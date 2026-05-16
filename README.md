# 🌽 SATO-Agro

**Sistema de Alerta Temprana y Prescripción para Mitigación de la Canícula**

SATO-Agro turns climate and satellite data into **actionable agricultural instructions** so smallholder corn and bean farmers in El Salvador can reduce crop losses from the canícula (mid-summer dry spell) before the damage becomes irreversible.

---

## 🚨 Problem

Smallholder corn and bean farmers in El Salvador face severe losses during the canícula. Climate data exists but it is:

- Technical and scattered across multiple sources
- Not translated into concrete actions
- Not delivered in a useful format to the farmer

**Result:** late decisions → crop losses.

---

## 💡 Solution

SATO-Agro converts SNET/MARN climate data into prescriptive alerts:

| Traditional Systems | SATO-Agro |
|---|---|
| Shows data | Indicates actions |
| General maps | Personalized recommendations |
| Monitoring | Prescription |
| Information | Decision |

---

## 🏗️ Architecture

```
Frontend / Mobile App
        ↓
   Flask Backend API (this repo)
        ↓
   SNET / MARN Upstream Sources
   ├── Live temperature stations (ArcGIS JSON)
   ├── Live wind stations (ArcGIS JSON)
   ├── 48-hour forecast (HTML scrape)
   ├── Weekly forecast PDF (URL extraction)
   └── Agro bulletin PDF (URL extraction)
```

The backend **proxies, normalizes, and caches** all upstream data so the frontend never calls SNET directly.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/observations/current` | All station observations |
| `GET` | `/api/v1/observations/current?station_id=4` | Single station |
| `GET` | `/api/v1/observations/nearest?lat=13.69&lon=-89.21` | Nearest station |
| `GET` | `/api/v1/forecast/48h` | 48-hour forecast |
| `GET` | `/api/v1/forecast/weekly` | Weekly forecast PDF metadata |
| `GET` | `/api/v1/agro/latest` | Latest agro bulletin PDF metadata |
| `GET` | `/api/v1/dashboard/summary?lat=13.69&lon=-89.21` | **Combined MVP payload** |
| `GET` | `/api/v1/stations` | Canonical station directory |
| `GET` | `/api/v1/features/current` | Flattened current features for frontend + LLM |
| `GET` | `/api/v1/documents/latest` | Latest forecast and bulletin documents |
| `GET` | `/api/v1/context/location?lat=13.69&lon=-89.21` | Canonical location context bundle |
| `GET` | `/api/v1/ai/tools/manifest` | LLM tool manifest |
| `POST` | `/api/v1/ai/tools/call` | Generic LLM function-calling endpoint |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+

### Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Run

```bash
python app.py
```

Server starts at **http://127.0.0.1:5000**

### Test

```bash
# Health check
curl http://127.0.0.1:5000/health

# Dashboard summary (the MVP endpoint)
curl "http://127.0.0.1:5000/api/v1/dashboard/summary?lat=13.69&lon=-89.21"
```

---

## 📁 Project Structure

```
ClimateAi/
├── README.md
├── agents.md
├── context.md                          # Problem statement & hackathon context
├── backend_hybrid_shape.md             # Canonical backend shape for frontend + AI
├── llm_function_calling_spec.md        # LLM tool contract
├── snet_api_roadmap.md                 # Verified upstream source roadmap
├── snet_latest_2026_endpoints.md       # Verified upstream source docs
├── snet_raw_endpoints.md               # Raw endpoint reference
└── backend/
    ├── app.py                          # Flask app factory
    ├── config.py                       # URLs, TTLs, HTTP defaults
    ├── requirements.txt
    ├── models/
    │   └── schemas.py                  # Dataclass response schemas
    ├── services/
    │   ├── snet_temperature.py         # Fetch live temp data
    │   ├── snet_wind.py                # Fetch live wind data
    │   ├── snet_forecast_48h.py        # Fetch 48h forecast HTML
    │   ├── snet_weekly_pdf.py          # Extract weekly PDF URL
    │   ├── snet_agro_pdf.py            # Extract agro PDF URL
    │   └── snet_station_metadata.py    # Resolve official station names
    ├── normalizers/
    │   ├── observations.py             # Merge temp + wind by station
    │   ├── forecasts.py                # Parse HTML → structured JSON
    │   ├── agro.py                     # Wrap PDF metadata
    │   └── canonical.py                # Shared frontend + AI records
    ├── routes/
    │   ├── health.py                   # /health
    │   ├── observations.py             # /api/v1/observations/*
    │   ├── forecasts.py                # /api/v1/forecast/*
    │   ├── agro.py                     # /api/v1/agro/*
    │   ├── dashboard.py                # /api/v1/dashboard/summary
    │   ├── canonical.py                # /api/v1/stations, /features, /documents, /context
    │   └── ai_tools.py                 # /api/v1/ai/tools/*
    ├── utils/
    │   ├── http.py                     # Shared session with retries
    │   ├── cache.py                    # TTL cache + stale fallback
    │   ├── time.py                     # Epoch → ISO conversion
    │   └── geo.py                      # Haversine nearest-station
    └── tests/
```

---

## 🔧 Configuration

All settings are in `backend/config.py` and can be overridden via environment variables:

| Variable | Default | Description |
|---|---|---|
| `FLASK_DEBUG` | `true` | Enable debug mode |
| `HTTP_TIMEOUT` | `10` | Upstream request timeout (seconds) |
| `HTTP_RETRIES` | `2` | Number of retries on failure |
| `CACHE_TTL_OBSERVATIONS` | `600` | Live data cache (10 min) |
| `CACHE_TTL_STATION_METADATA` | `86400` | Station metadata cache (24 hours) |
| `CACHE_TTL_FORECAST_48H` | `1800` | Forecast cache (30 min) |
| `CACHE_TTL_WEEKLY_PDF` | `21600` | Weekly PDF cache (6 hours) |
| `CACHE_TTL_AGRO_PDF` | `21600` | Agro PDF cache (6 hours) |

---

## 🛡️ Resilience

- **Cache fallback**: If SNET goes down, the API serves the last known-good data with `"stale": true`
- **Automatic retries**: 2 retries with exponential backoff on 5xx errors
- **Independent caching**: Each data source has its own TTL — one failing source doesn't break the others

---

## 🎯 Target Users

- **Primary**: Agricultural extension workers, cooperatives, technical staff
- **Beneficiary**: Smallholder corn and bean farmers

---

## 📄 License

Hackathon project — Environment & Climate Risk track.
