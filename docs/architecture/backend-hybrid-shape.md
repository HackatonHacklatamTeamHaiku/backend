# Hybrid Backend Shape

This backend now exposes a shared surface for:

- frontend UI
- explainable risk workflows
- tool-calling assistants
- document discovery for RAG

The goal is one backend truth with a small number of clear entrypoints.

---

## Primary API Surface

These are the preferred routes for new frontend and assistant work.

### `GET /api/weather/observed`

Observed weather bundle for a point.

Returns fields like:

- `location`
- `nearest_rain_station`
- `nearest_temperature_station`
- `nearest_wind_station`
- `rain_recent_mm`
- `temperature_current_c`
- `temperature_max_c`
- `temperature_min_c`
- `wind_speed_kmh`
- `wind_direction_deg`
- `is_raining`
- `observed_at`
- `warnings`
- `sources_used`

Use cases:

- dashboard weather cards
- location-aware observed conditions
- freshness and confidence indicators

---

### `GET /api/weather/forecast`

Forecast or scenario bundle for a point and date.

Returns fields like:

- `target_date`
- `horizon`
- `rain_sum_mm`
- `rain_probability_max`
- `temp_max_c`
- `temp_min_c`
- `wind_max_kmh`
- `et0_sum_mm`
- `soil_moisture_model`
- `warnings`

Horizons currently used by the backend:

- `present`
- `1_3_days`
- `4_7_days`
- `8_16_days`
- `gt_16_days`

Use cases:

- forecast cards
- planning views
- slider-driven date exploration

Important:

- `gt_16_days` must be treated as scenario, not precise forecast

---

### `GET /api/geo/context`

Territorial context bundle for a point.

Returns fields like:

- `municipality`
- `municipality_code`
- `canton`
- `basin_id`
- `soil_context`
- `climate_outlook_context`
- `nearest_*_station`
- `warnings`
- `sources_used`

Use cases:

- parcel onboarding
- territorial context panels
- seasonal dryness and soil modifiers

---

### `GET /api/risk/assessment`

Explainable agroclimatic risk result for crop, sowing date, location, and optional target date.

Returns fields like:

- `risk_score`
- `risk_level`
- `confidence`
- `recommendations`
- `assumptions`
- `sources_used`
- `plant_state`
- `climate_state`
- `risk_factors`
- `risk_overrides`
- `secondary_alerts`
- `observed_weather`
- `forecast_weather`
- `geo_context`
- `official_context`

Use cases:

- dashboard main card
- preventive advisory UI
- assistant grounding for crop-specific answers

Important:

- use `plant_state`, not `phenology`, as the current backend field

---

### `GET /api/llm/context`

Runtime context bundle for assistants.

Full mode requires:

- `crop`
- `sowing_date`
- `lat`
- `lon`

Optional:

- `target_date`

Fallback mode:

- if only `target_date` is present, backend returns `official_context` only

Returns fields like:

- `current_datetime`
- `timezone`
- `user_inputs`
- `ui_state`
- `missing_required_user_data`
- `plant_state`
- `observed_weather`
- `forecast_weather`
- `risk_assessment`
- `recommendations`
- `official_context`
- `sources_used`
- `source_policy`

Use cases:

- system/runtime context injection for assistants
- chat orchestration

---

### `POST /api/llm/chat`

Backend-managed conversational entrypoint backed by OpenRouter.

Accepts fields like:

- `message`
- `model`
- `crop`
- `sowing_date`
- `lat`
- `lon`
- `target_date`
- `conversation`

Returns fields like:

- `reply`
- `runtime_context`
- `tool_calls`
- `model`
- `requested_model`
- `routing_models`
- `finish_reason`
- `openrouter_metadata`

Use cases:

- product chat UI
- model selection from frontend
- one-call backend-managed tool orchestration

Important:

- if frontend supplies `model`, backend routes to that model first
- backend keeps `mistralai/mistral-medium-3.1` as fallback
- this route is preferred when the app wants a simple chat contract instead of external tool orchestration

---

### `POST /api/llm/explain`

Narrative explanation endpoint.

Minimum useful input:

- `risk_assessment`

Recommended additional input:

- `plant_state`
- `official_context`
- `recommendations`
- `audience`

Use cases:

- “Explain this risk” UI action
- assistant post-processing

---

## Compatibility Surface

These routes still exist intentionally:

### `GET /api/v1/documents/latest`

Canonical latest document registry for:

- `forecast_48h`
- `weekly_forecast_pdf`
- `agro_bulletin_pdf`

Use cases:

- RAG indexing
- document widgets
- citation and retrieval workflows

### `GET /api/v1/ai/tools/manifest`
### `POST /api/v1/ai/tools/call`

Compatibility tool layer for assistants.

Current public semantic tools:

- `getRiskAssessment`
- `getWeatherObserved`
- `getOfficialContext`
- `getPhenologyContext`
- `buildRuntimeContext`
- `explainRecommendation`

---

## Retired Public Routes

Do not build new frontend or agent integrations on these:

- `/api/v1/observations/current`
- `/api/v1/observations/nearest`
- `/api/v1/forecast/48h`
- `/api/v1/forecast/weekly`
- `/api/v1/agro/latest`
- `/api/v1/agro/advisory`
- `/api/v1/dashboard/summary`
- `/api/v1/stations`
- `/api/v1/features/current`
- `/api/v1/context/location`

Some helper logic still exists internally for compatibility and composition, but those routes are no longer part of the intended public contract.

---

## Consumer Strategy

### Frontend

Prefer:

- `/api/weather/observed`
- `/api/weather/forecast`
- `/api/geo/context`
- `/api/risk/assessment`
- `/api/llm/chat`
- `/api/llm/explain`

Why:

- fewer dead branches
- better alignment with the manifest model
- direct access to plant, geo, and risk context

### Tool-calling assistants

Prefer:

- `/api/v1/ai/tools/manifest`
- `/api/v1/ai/tools/call`

Use:

- `/api/llm/context` when the app wants to pre-compose runtime context itself
- `buildRuntimeContext` through `/api/v1/ai/tools/call` when a tool-calling assistant needs the same backend-composed runtime context

Avoid:

- rebuilding the same tool loop in frontend if `/api/llm/chat` already fits the product flow

### RAG

Use:

- `/api/v1/documents/latest` as the document registry

Then:

1. download source
2. extract text
3. chunk with metadata
4. store embeddings keyed by `document_id`, `document_type`, and issue date

---

## Design Rules

- keep upstream SNET and Open-Meteo payloads behind the backend
- keep frontend on the manifest-aligned public surface
- keep product chat on `/api/llm/chat` unless an external agent truly needs raw tools
- keep tool-calling assistants on the semantic tool layer
- treat `gt_16_days` as scenario, not precise forecast
- treat modeled soil moisture as context, not direct field measurement
- keep `plant_state` and `risk_assessment` as the main decision objects for UI and assistant flows
