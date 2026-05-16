# Agents

## Project Context

This is **SATO-Agro** — a hackathon project for the Environment & Climate Risk track. It converts SNET/MARN climate data from El Salvador into actionable agricultural prescriptions to help smallholder corn and bean farmers mitigate crop losses during the canícula (mid-summer dry spell).

## Architecture Overview

The project follows a **backend-first architecture**: a Python Flask API that proxies, normalizes, and caches upstream government climate data (SNET/MARN), exposing clean JSON endpoints that any frontend or mobile app can consume.

```
Frontend → Flask API → Service Layer → Normalizer → Cache → JSON Response
```

## Tech Stack

- **Backend**: Python 3.10+, Flask 3.1
- **HTTP**: requests with retry/timeout via shared session
- **Parsing**: BeautifulSoup4 (HTML scraping), regex (PDF URL extraction)
- **Caching**: cachetools TTLCache with stale-fallback pattern
- **Schemas**: stdlib dataclasses (not Pydantic — see note below)
- **CORS**: flask-cors for frontend integration

> **Note**: Pydantic was in the original plan but pydantic-core's Rust extension doesn't compile on Python 3.14. We use `dataclasses` + `dataclasses.asdict()` instead, which produces identical JSON with zero compilation dependencies.

## Key Design Patterns

### 5-Layer Architecture

1. **Routes** (`routes/`) — Flask blueprints, one per domain. Handle HTTP request/response only.
2. **Services** (`services/`) — One file per upstream source. Fetch raw data, nothing else.
3. **Normalizers** (`normalizers/`) — Convert raw upstream formats into internal schemas.
4. **Cache** (`utils/cache.py`) — Per-source TTL cache with last-known-good fallback.
5. **Schemas** (`models/schemas.py`) — Dataclasses defining every JSON response shape.

### Cache + Stale Fallback

Every data source has its own `DataCache` instance with an independent TTL. If an upstream fetch fails, the route returns the last successful payload with `"stale": true` in the response metadata. The frontend never sees a blank screen.

### Upstream Sources

| Source | Type | Service File |
|---|---|---|
| Temperature stations | ArcGIS JSON | `snet_temperature.py` |
| Wind stations | ArcGIS JSON | `snet_wind.py` |
| 48-hour forecast | HTML page | `snet_forecast_48h.py` |
| Weekly forecast PDF | HTML scrape → PDF URL | `snet_weekly_pdf.py` |
| Agro bulletin PDF | HTML scrape → PDF URL | `snet_agro_pdf.py` |

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Health check |
| `GET /api/v1/observations/current` | All stations (temp + wind merged) |
| `GET /api/v1/observations/nearest?lat=&lon=` | Nearest station via Haversine |
| `GET /api/v1/forecast/48h` | Parsed 48h forecast |
| `GET /api/v1/forecast/weekly` | Weekly PDF metadata |
| `GET /api/v1/agro/latest` | Agro bulletin PDF metadata |
| `GET /api/v1/dashboard/summary?lat=&lon=` | **Combined MVP payload** |

## File Map

```
backend/
├── app.py                    # Flask app factory, blueprint registration, CORS
├── config.py                 # Centralized config (URLs, TTLs, HTTP defaults)
├── requirements.txt          # Pure-Python dependencies
├── models/schemas.py         # All dataclass response schemas
├── services/                 # One file per upstream source (fetch only)
├── normalizers/              # Raw → internal schema conversion
├── routes/                   # Flask blueprints (one per domain)
├── utils/
│   ├── http.py               # Shared requests.Session with retries
│   ├── cache.py              # DataCache class (TTL + stale fallback)
│   ├── time.py               # Epoch ms → ISO, El Salvador TZ (UTC-6)
│   └── geo.py                # Haversine distance, find_nearest()
└── tests/
```

## How to Run

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python app.py                 # Starts on http://127.0.0.1:5000
```

## Adding a New Data Source

1. Create `services/snet_new_source.py` — fetch raw data
2. Create or update a normalizer in `normalizers/` — convert to schema
3. Add a dataclass to `models/schemas.py` if needed
4. Create a route in `routes/` with its own `DataCache` instance
5. Register the blueprint in `app.py`

## Response Envelope

Every endpoint returns the same envelope:

```json
{
  "data": { ... },
  "meta": {
    "cached": true,
    "stale": false,
    "upstream_status": "ok",
    "fetched_at": "2026-05-16T03:03:40+00:00"
  }
}
```

When `stale: true`, the data is from a previous successful fetch and the upstream source may be down.
