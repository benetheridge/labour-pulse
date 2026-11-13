# UK Labour Pulse

A small live dashboard for my website. It shows ONS headline labour-market series
and the share of UK job adverts on Adzuna that mention AI.

**How it works**

1. `fetch_data.py` runs every morning on GitHub Actions. It pulls ONS series
   (no key needed) and Adzuna counts (secret key), then writes `data.json`.
2. `index.html` is a static page on GitHub Pages that reads `data.json`.
3. Google Sites embeds that page.

Adzuna can only report today's counts, so the AI trend line builds up one day
at a time from the first run.

## Setup (about 15 minutes)

1. **Create a GitHub repo.** Make a new public repo, e.g. `labour-pulse`, and upload
   all these files, keeping the `.github/workflows/` folder.
2. **Turn on Pages.** Go to Settings → Pages → Source: *Deploy from a branch* →
   `main` / root. Your page will be at `https://<username>.github.io/labour-pulse/`.
3. **Add Adzuna keys (optional).** Sign up free at developer.adzuna.com. Then go to
   Settings → Secrets and variables → Actions → *New repository secret*, and add
   `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. Without them, the AI section simply doesn't
   appear.
4. **Run it once.** Go to Actions → *Update labour pulse data* → *Run workflow*. This
   replaces the sample `data.json` with real figures. After that it runs daily at
   07:17 UTC.
5. **Embed in Google Sites.** Choose Insert → Embed → *By URL*, paste the Pages URL,
   choose *Whole page*, then drag the box to about 1000 px tall.

## Changing things

- **Series:** edit `ONS_SERIES` in `fetch_data.py`. Each entry needs a CDID from
  the LMS dataset, e.g. `MGSX`.
- **AI definition:** edit `AI_TERMS`. Adzuna counts an ad if it contains *any* of
  the words.
- **Tests:** `pip install pytest requests && pytest`. These run offline against
  mocked APIs.
- **Preview:** `python make_sample.py` writes invented demo data, flagged
  `"sample": true`. The real fetcher ignores it.

## Caveats

- "AI" as a keyword is broad. It will also catch ads that only mention AI in
  passing. Treat the series as a pulse, not a measure.
- The ONS API is in beta. The script tries the beta endpoint first, then the legacy
  `www.ons.gov.uk/.../data` URL. If ONS fails, the last good values are kept.
- The Adzuna free tier is about 1,000 calls a month. This uses 4 a day.
