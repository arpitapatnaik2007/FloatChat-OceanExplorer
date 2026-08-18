# FloatChat Python backend

FastAPI service that powers the FloatChat frontend: natural-language ARGO queries,
oceanographic aggregations, chart series, and CSV export. Storage is SQLite,
seeded with deterministic synthetic ARGO profiles (48 floats, ~700 profiles,
16 standard depth levels each) so it runs with zero external setup.

## Run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Status + row counts |
| GET | `/api/languages` | Locales for the voice/language selector |
| GET | `/api/floats` | Float list (`basin`, `bgc_only`, `active_only`, `limit`) |
| GET | `/api/floats/{wmo}/profiles` | Cycles for one float |
| GET | `/api/profiles/{id}` | One profile with all depth levels |
| GET | `/api/charts/overview` | All dashboard series for a region/date window |
| POST | `/api/chat` | Natural language → SQL plan → data → answer |
| GET | `/api/export.csv` | CSV export of matching profiles |

### Example chat call

```bash
curl -s localhost:8000/api/chat -H 'content-type: application/json' \
  -d '{"message":"Show me salinity profiles near the equator in March 2023","language":"en-IN"}'
```

Response contains `answer` (markdown narration), `plan` (parsed intent + the exact
SQL and params executed), `stats`, `charts` (series ready for Recharts/Chart.js),
`table`, and `citations`.

## Modules

- `app/db.py` — schema, connection helper, synthetic ARGO seeding
- `app/nl2sql.py` — rule-based intent/region/date parsing → parameterised SQL
- `app/analytics.py` — depth curves, T–S diagram, monthly series, heat content, nearest floats
- `app/answers.py` — deterministic narration from real aggregates (halocline, OMZ, SCM depths)
- `app/llm.py` — optional multilingual polish via `LOVABLE_API_KEY` or `OPENAI_API_KEY`
- `app/main.py` — FastAPI app, CORS, routes

## Config

| Env var | Default | Notes |
| --- | --- | --- |
| `FLOATCHAT_CORS_ORIGINS` | `http://localhost:8080,...` | Comma-separated allowed origins |
| `LOVABLE_API_KEY` / `OPENAI_API_KEY` | unset | Enables LLM answer rewriting in the user's language |

All SQL uses bound parameters; the NL layer never interpolates user text into SQL.
Swapping the synthetic seed for real ARGO NetCDF only requires replacing `seed()`
with an ingest that writes to the same three tables.