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
| `GET` | `/api/weather/observed?lat=13.69&lon=-89.21` | Manifest-aligned observed weather bundle |
| `GET` | `/api/weather/forecast?lat=13.69&lon=-89.21&target_date=2026-05-20` | Manifest-aligned Open-Meteo forecast bundle |
| `GET` | `/api/geo/context?lat=13.69&lon=-89.21` | Manifest-aligned geo context bundle |
| `GET` | `/api/risk/assessment?crop=maiz&sowing_date=2026-05-20&lat=13.69&lon=-89.21` | Manifest-aligned explainable risk assessment |
| `GET` | `/api/auth/me` | Current authenticated user + linked producer profile |
| `GET` | `/api/llm/context?...` | Runtime LLM context contract |
| `POST` | `/api/llm/chat` | Backend-managed chat with OpenRouter + semantic tool loop |
| `POST` | `/api/llm/explain` | Backend-generated plain-language explanation |
| `GET` | `/api/v1/documents/latest` | Compatibility route for latest forecast and bulletin documents |
| `GET` | `/api/v1/ai/tools/manifest` | Compatibility LLM tool manifest |
| `POST` | `/api/v1/ai/tools/call` | Compatibility generic function-calling endpoint |

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

Create the local env file:

```bash
cp backend/.env.example backend/.env
```

On Windows PowerShell:

```powershell
Copy-Item backend\\.env.example backend\\.env
```

### Run

```bash
python app.py
```

Server starts at **http://127.0.0.1:5000**

### Supabase

The runtime backend uses Supabase REST/PostgREST, not a direct PostgreSQL connection. Configure these values in `backend/.env`:

```env
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
```

Keep the service role key server-side only. It must not be exposed to frontend clients.

Apply the schema to the cloud database through the Supabase SQL Editor or CLI. The legacy direct-SQL migration script still expects `DATABASE_URL`:

```bash
python backend/scripts/apply_migrations.py
```

Verify the mounted database:

```bash
python backend/scripts/verify_database.py
```

### Auth

All `/api/*` routes now require:

```http
Authorization: Bearer <supabase_access_token>
```

Public exceptions:

- `/`
- `/health`

The backend validates Supabase JWTs using the project's JWKS and exposes:

```http
GET /api/auth/me
```

to return the authenticated user plus the linked `profiles` row.

To seed a developer test user into Supabase Auth and `public.profiles`:

```bash
python backend/scripts/seed_test_user.py
```

Default dev credentials:

- email: `<test-email>`
- password: `<test-password>`

The frontend still needs its own `SUPABASE_URL` and publishable key to perform login directly against Supabase Auth.

### Test

```bash
# Health check
curl http://127.0.0.1:5000/health

# Backend auth bootstrap
curl "http://127.0.0.1:5000/api/auth/me" \
  -H "Authorization: Bearer <supabase_access_token>"

# Risk assessment
curl "http://127.0.0.1:5000/api/risk/assessment?crop=maiz&sowing_date=2026-05-20&lat=13.69&lon=-89.21&target_date=2026-08-15"

# Chat
curl -X POST "http://127.0.0.1:5000/api/llm/chat" \
  -H "Authorization: Bearer <supabase_access_token>" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"como va mi maiz\",\"crop\":\"maiz\",\"sowing_date\":\"2026-05-10\",\"lat\":13.8,\"lon\":-89.1833,\"target_date\":\"2026-05-16\"}"
```

### OpenRouter

The backend now supports backend-managed chat through OpenRouter.

Expected environment variables:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (optional if frontend always sends `model`)
- `OPENROUTER_FALLBACK_MODELS`
- `LLM_SYSTEM_PROMPT_PATH` (optional)

Current expected product behavior:

- frontend may send `model` to `/api/llm/chat`
- backend routes to that model first
- backend keeps `mistralai/mistral-medium-3.1` as fallback
- backend owns the semantic tool loop using:
  - `getRiskAssessment`
  - `getOfficialContext`
  - `getPhenologyContext`
  - `explainRecommendation`

---

## 📁 Project Structure

```
ClimateAi/
├── README.md
├── agents.md
├── docs/
│   ├── project/
│   │   └── context.md                  # Problem statement & hackathon context
│   ├── architecture/
│   │   └── backend-hybrid-shape.md     # Canonical backend shape for frontend + AI
│   ├── ai/
│   │   └── llm-function-calling-spec.md# LLM tool + chat contract
│   ├── data-sources/
│   │   ├── snet-api-roadmap.md         # Verified upstream source roadmap
│   │   ├── snet-latest-2026-endpoints.md
│   │   └── snet-raw-endpoints.md
│   └── database/
│       ├── database-capture-plan.md
│       └── database-schema.dbml
└── backend/
    ├── app.py                          # Flask app factory
    ├── config.py                       # URLs, TTLs, HTTP defaults
    ├── requirements.txt
    ├── models/
    │   └── schemas.py                  # Dataclass response schemas
    ├── services/
    │   ├── openrouter_llm.py          # OpenRouter chat orchestration
    │   ├── semantic_tools.py          # Shared semantic tool execution
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
    │   ├── weather.py                  # /api/weather/*
    │   ├── geo.py                      # /api/geo/context
    │   ├── risk.py                     # /api/risk/assessment
    │   ├── llm.py                      # /api/llm/*
    │   ├── canonical.py                # /api/v1/documents/latest
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
