"""Offline tests: mock the ONS and Adzuna APIs and check data.json is built right."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch_data as fd  # noqa: E402


def fake_ons_page(cdid):
    months = [{"date": f"2026 {m}", "value": str(4.0 + i / 10)}
              for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN"])]
    months.append({"date": "2026 JUL", "value": ""})  # unpublished cell: skipped
    return {"months": months,
            "description": {"cdid": cdid, "nextRelease": "17 November 2026"}}


def fake_get_json(url, params=None):
    params = params or {}
    if url.endswith("/search"):
        cdid = params["cdids"].lower()
        return {"items": [{"uri": f"/x/timeseries/{cdid}/emp"},
                          {"uri": f"/x/timeseries/{cdid}/lms"}]}
    if url.endswith("/v1/data"):
        if "kac3" in params["uri"]:
            raise RuntimeError("beta API down")  # forces legacy fallback
        return fake_ons_page(params["uri"].split("/")[-2])
    if url.startswith(fd.ONS_LEGACY):
        return fake_ons_page("kac3")
    if "search/1" in url:
        return {"count": 1200 if "what_or" in params else 60000}
    if "geodata" in url:
        ai = "what_or" in params
        return {"locations": [
            {"location": {"display_name": "London"}, "count": 500 if ai else 10000},
            {"location": {"display_name": "Wales"}, "count": 30 if ai else 3000},
        ]}
    raise AssertionError(url)


def test_full_run(tmp_path, monkeypatch):
    monkeypatch.setattr(fd, "_get_json", fake_get_json)
    monkeypatch.setattr(fd, "OUT", tmp_path / "data.json")
    monkeypatch.setenv("ADZUNA_APP_ID", "x")
    monkeypatch.setenv("ADZUNA_APP_KEY", "y")
    fd.main()
    d = json.loads((tmp_path / "data.json").read_text())

    assert len(d["ons"]["series"]) == len(fd.ONS_SERIES)
    s = d["ons"]["series"][0]
    assert s["latest"] == {"period": "2026 Jun", "value": 4.5}
    assert s["change"] == 0.1
    assert s["source"].endswith("/lms")
    assert d["ons"]["next_release"] == "17 November 2026"

    a = d["adzuna"]
    assert a["share"] == 2.0
    assert [r["name"] for r in a["regions"]] == ["London", "Wales"]
    assert a["regions"][0]["share"] == 5.0

    # second run same day replaces today's point rather than duplicating it
    fd.main()
    d2 = json.loads((tmp_path / "data.json").read_text())
    assert len(d2["adzuna"]["history"]) == 1


def test_no_keys_skips_adzuna(tmp_path, monkeypatch):
    monkeypatch.setattr(fd, "_get_json", fake_get_json)
    monkeypatch.setattr(fd, "OUT", tmp_path / "data.json")
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    fd.main()
    assert json.loads((tmp_path / "data.json").read_text())["adzuna"] is None
