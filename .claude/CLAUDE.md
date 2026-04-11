# Pharma Monitor UZ

Мониторинг дистрибьюции медтехники Prolife и конкурентов по аптекам Узбекистана.

## Session protocol

**START**: Read this file + `git log --oneline -5`.
**END**: Update "Last session" below.

## Quick start

```bash
cd ~/Documents/Claude/Projects/pharma-monitor-uz
# Scrape fresh data
python run_scrape.py
# Launch dashboard
streamlit run src/pharma_monitor/dashboard/app.py
```

## Stack

Python + httpx + SQLite + Streamlit + Plotly. Deployed on Vercel (has `.vercel/` dir).

## ArzonApteka API

- `POST /api/v4/{lang}/trigrams` (FormData) — text search, returns product IDs
- `POST /api/v4/{lang}/search` (JSON) — pharmacy/price data by medicine IDs
- `GET /api/v4/{lang}/pharmacies` — all pharmacies list
- API key = `md5(BASE_URL + endpoint + "Nx3WWr")`
- Medicine IDs are NOT sequential — discover via trigrams

## Key files

| File | Purpose |
|---|---|
| `src/pharma_monitor/scrapers/arzonapteka.py` | API client |
| `src/pharma_monitor/db/database.py` | SQLite schema + CRUD |
| `src/pharma_monitor/analytics/metrics.py` | Distribution KPIs |
| `src/pharma_monitor/dashboard/app.py` | Streamlit dashboard |
| `run_scrape.py` | CLI entry point |

## Data (last scrape 2026-04-03)

- 434 products, 1735 pharmacies, 33958 observations
- Prolife: 13 products / 489 pharmacies
- OMRON: 29 products / 374 pharmacies
- B.Well: 27 products / 636 pharmacies
- Microlife: 10 products / 33 pharmacies

## Known issues

- `run_dashboard.bat` won't work on Mac — use `streamlit run` directly
- Local-only dirs (data/, api/, recon_output/) are untracked in git

## Last session

**Status:** Working, needs fresh scrape to update data.
