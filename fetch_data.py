"""Fetch UK labour-market data for the Labour Pulse widget and write data.json.

Two sources:
  * ONS headline labour-market series (no key needed).
  * Adzuna UK job adverts: share of ads mentioning AI terms, nationally and
    by region (needs ADZUNA_APP_ID / ADZUNA_APP_KEY env vars; skipped if absent).

Run daily by GitHub Actions. Each run appends today's Adzuna reading to a
running history, so the "AI pulse" sparkline grows over time.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import requests

OUT = Path(__file__).with_name("data.json")
TIMEOUT = 30
HEADERS = {"User-Agent": "labour-pulse-widget (academic personal website)"}

# --------------------------------------------------------------------------
# ONS
# --------------------------------------------------------------------------
# cdid, label, unit, which direction counts as "good", fallback page uri
ONS_SERIES = [
    ("MGSX", "Unemployment rate (16+)", "%", "down",
     "/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms"),
    ("LF24", "Employment rate (16-64)", "%", "up",
     "/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/timeseries/lf24/lms"),
    ("AP2Y", "Vacancies", "k", "up",
     "/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/timeseries/ap2y/lms"),
    ("KAC3", "Pay growth (total, 3m y/y)", "%", "up",
     "/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kac3/lms"),
    ("A3WW", "Real pay growth (3m y/y)", "%", "up",
     "/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/a3ww/lms"),
    ("LF2S", "Inactivity rate (16-64)", "%", "down",
     "/employmentandlabourmarket/peoplenotinwork/economicinactivity/timeseries/lf2s/lms"),
]
ONS_BETA = "https://api.beta.ons.gov.uk/v1"
ONS_LEGACY = "https://www.ons.gov.uk"
HISTORY_POINTS = 36  # months shown in each sparkline


def _get_json(url: str, params: dict | None = None) -> dict:
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def resolve_ons_uri(cdid: str, fallback: str) -> str:
    """Find the LMS page uri for a series via the ONS search API."""
    try:
        res = _get_json(f"{ONS_BETA}/search",
                        {"content_type": "timeseries", "cdids": cdid})
        for item in res.get("items", []):
            uri = item.get("uri", "")
            if uri.rstrip("/").endswith("/lms"):
                return uri
    except Exception as exc:  # noqa: BLE001 - fall back quietly
        print(f"  search failed for {cdid}: {exc}", file=sys.stderr)
    return fallback


def fetch_ons_page(uri: str) -> dict:
    """Get the timeseries JSON, trying the beta data API then the legacy URL."""
    errors = []
    for url, params in ((f"{ONS_BETA}/data", {"uri": uri}),
                        (f"{ONS_LEGACY}{uri}/data", None)):
        try:
            return _get_json(url, params)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {exc}")
    raise RuntimeError("; ".join(errors))


def parse_ons(page: dict) -> tuple[list[dict], dict]:
    """Return (observations, description) from an ONS timeseries page."""
    obs = page.get("months") or page.get("quarters") or page.get("years") or []
    clean = []
    for o in obs:
        val = str(o.get("value", "")).strip()
        try:
            clean.append({"period": o.get("date", "").title(), "value": float(val)})
        except ValueError:
            continue
    return clean, page.get("description", {})


def get_ons() -> dict:
    out = []
    next_release = None
    for cdid, label, unit, good, fallback in ONS_SERIES:
        try:
            uri = resolve_ons_uri(cdid, fallback)
            obs, desc = parse_ons(fetch_ons_page(uri))
            if not obs:
                raise RuntimeError("no observations")
            hist = obs[-HISTORY_POINTS:]
            latest, prev = hist[-1], hist[-2] if len(hist) > 1 else None
            out.append({
                "id": cdid, "label": label, "unit": unit, "good": good,
                "latest": latest,
                "change": round(latest["value"] - prev["value"], 2) if prev else None,
                "history": hist,
                "source": f"{ONS_LEGACY}{uri}",
            })
            next_release = next_release or desc.get("nextRelease")
            print(f"  ONS {cdid}: {latest}")
        except Exception as exc:  # noqa: BLE001 - one bad series shouldn't sink the run
            print(f"  ONS {cdid} failed: {exc}", file=sys.stderr)
    return {"series": out, "next_release": next_release}


# --------------------------------------------------------------------------
# Adzuna
# --------------------------------------------------------------------------
ADZUNA = "https://api.adzuna.com/v1/api/jobs/gb"
# An ad counts as "AI" if it mentions any of these words (Adzuna what_or).
AI_TERMS = "AI LLM ChatGPT GenAI Copilot"


def _adzuna(endpoint: str, creds: dict, **params) -> dict:
    return _get_json(f"{ADZUNA}/{endpoint}", {**creds, **params})


def get_adzuna(creds: dict, previous: dict | None) -> dict:
    total = _adzuna("search/1", creds, results_per_page=1)["count"]
    ai = _adzuna("search/1", creds, results_per_page=1, what_or=AI_TERMS)["count"]

    geo_all = _adzuna("geodata", creds, location0="UK")
    geo_ai = _adzuna("geodata", creds, location0="UK", what_or=AI_TERMS)
    totals = {g["location"]["display_name"]: g["count"]
              for g in geo_all.get("locations", [])}
    regions = []
    for g in geo_ai.get("locations", []):
        name = g["location"]["display_name"]
        if totals.get(name):
            regions.append({"name": name, "ai": g["count"], "total": totals[name],
                            "share": round(100 * g["count"] / totals[name], 2)})
    regions.sort(key=lambda r: r["share"], reverse=True)

    today = dt.date.today().isoformat()
    share = round(100 * ai / total, 2) if total else None
    history = [h for h in (previous or {}).get("history", []) if h["date"] != today]
    history.append({"date": today, "share": share, "ai": ai, "total": total})
    print(f"  Adzuna: {ai:,} of {total:,} ads ({share}%)")
    return {"terms": AI_TERMS.split(), "total": total, "ai": ai, "share": share,
            "regions": regions, "history": history[-365:]}


# --------------------------------------------------------------------------
def main() -> None:
    previous = json.loads(OUT.read_text()) if OUT.exists() else {}
    if previous.get("sample"):
        previous = {}  # don't carry demo numbers into real history

    print("Fetching ONS...")
    ons = get_ons()
    if not ons["series"] and previous.get("ons"):
        print("  ONS unavailable; keeping previous values", file=sys.stderr)
        ons = previous["ons"]

    adzuna = previous.get("adzuna")
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if app_id and app_key:
        print("Fetching Adzuna...")
        try:
            adzuna = get_adzuna({"app_id": app_id, "app_key": app_key}, adzuna)
        except Exception as exc:  # noqa: BLE001
            print(f"  Adzuna failed, keeping previous: {exc}", file=sys.stderr)
    else:
        print("No Adzuna keys set; skipping AI pulse.")

    data = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
            "ons": ons, "adzuna": adzuna}
    OUT.write_text(json.dumps(data, indent=1))
    print(f"Wrote {OUT}")
    if not ons["series"]:
        sys.exit("No ONS data at all - failing so the Action flags it.")


if __name__ == "__main__":
    main()
