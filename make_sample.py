"""Write a clearly-flagged SAMPLE data.json so the widget can be previewed
before the first real run. The numbers are invented, not ONS/Adzuna figures.
The first real run of fetch_data.py overwrites this file."""
import datetime as dt
import json
import math
import random
from pathlib import Path

random.seed(7)
months = []
d = dt.date(2023, 9, 1)
for _ in range(36):
    months.append(d.strftime("%Y %b"))
    d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def walk(start, step, drift=0.0, nd=1):
    v, out = start, []
    for i, m in enumerate(months):
        v += drift + random.uniform(-step, step)
        out.append({"period": m, "value": round(v, nd)})
    return out


specs = [("MGSX", "Unemployment rate (16+)", "%", "down", walk(4.2, 0.08, 0.02)),
         ("LF24", "Employment rate (16-64)", "%", "up", walk(75.1, 0.12, -0.01)),
         ("AP2Y", "Vacancies", "k", "up", walk(950, 12, -6, 0)),
         ("KAC3", "Pay growth (total, 3m y/y)", "%", "up", walk(7.5, 0.2, -0.1)),
         ("A3WW", "Real pay growth (3m y/y)", "%", "up", walk(1.0, 0.25, 0.0)),
         ("LF2S", "Inactivity rate (16-64)", "%", "down", walk(21.8, 0.1, 0.0))]
series = []
for cdid, label, unit, good, hist in specs:
    series.append({"id": cdid, "label": label, "unit": unit, "good": good,
                   "latest": hist[-1],
                   "change": round(hist[-1]["value"] - hist[-2]["value"], 2),
                   "history": hist, "source": "https://www.ons.gov.uk"})

regions = ["London", "South East England", "Eastern England", "Scotland",
           "North West England", "South West England", "West Midlands",
           "Yorkshire And The Humber", "East Midlands", "Wales",
           "North East England", "Northern Ireland"]
reg = []
for i, r in enumerate(regions):
    total = random.randint(20000, 220000) if i else 260000
    share = round(6.5 - i * 0.35 + random.uniform(-0.2, 0.2), 2)
    reg.append({"name": r, "total": total, "ai": int(total * share / 100), "share": share})
hist, day = [], dt.date.today() - dt.timedelta(days=89)
for i in range(90):
    s = round(3.6 + i * 0.006 + 0.15 * math.sin(i / 6) + random.uniform(-0.05, 0.05), 2)
    hist.append({"date": (day + dt.timedelta(days=i)).isoformat(), "share": s,
                 "ai": int(1_050_000 * s / 100), "total": 1_050_000})
data = {"sample": True,
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "ons": {"series": series, "next_release": "17 November 2026"},
        "adzuna": {"terms": ["AI", "LLM", "ChatGPT", "GenAI", "Copilot"],
                   "total": hist[-1]["total"], "ai": hist[-1]["ai"],
                   "share": hist[-1]["share"], "regions": reg, "history": hist}}
Path(__file__).with_name("data.json").write_text(json.dumps(data, indent=1))
print("sample data.json written")
