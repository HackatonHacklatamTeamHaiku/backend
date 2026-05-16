# Hybrid Backend Shape

This backend now exposes a shared canonical layer for:

- frontend components
- ML feature ingestion
- LLM function calling
- RAG document retrieval metadata

The goal is one source of truth with different views of the same data, instead of separate backend shapes per consumer.

## Canonical API Surface

### `GET /api/v1/stations`
Human-readable station directory for UI selectors, map markers, and lookup.

Returns:
- `station_id`
- `station_code`
- `station_name`
- `station_label`
- `lat`
- `lon`
- `source`

Use cases:
- populate frontend dropdowns
- resolve nearest station labels
- map stable IDs to plain names for AI tools

### `GET /api/v1/features/current`
Flattened current observation rows for ML and analytics.

Returns one row per station with:
- station identity fields
- coordinates
- UTC and local timestamps
- `temperature_current_c`
- `temperature_max_c`
- `temperature_min_c`
- `temperature_diurnal_range_c`
- `wind_direction_deg`
- `wind_speed`
- completeness flags
- `observation_age_minutes`

Use cases:
- feed batch feature jobs
- power frontend tables/cards without nested parsing
- expose clean numeric tool outputs to an LLM

### `GET /api/v1/documents/latest`
Canonical latest document list for forecast and bulletin sources.

Current records:
- `forecast_48h`
- `weekly_forecast_pdf`
- `agro_bulletin_pdf`

Each record includes:
- `document_id`
- `document_type`
- `title`
- `summary`
- `url`
- `issued_at`
- `last_modified`
- `content_text` when available

Use cases:
- RAG indexing
- latest-document widgets in the frontend
- AI retrieval metadata before chunking

### `GET /api/v1/context/location?lat=&lon=`
Single context bundle for a location.

Returns:
- `location`
- `station`
- `observation`
- `features`
- `documents`
- `meta`

Use cases:
- one-call frontend summary cards
- LLM tool calling for location-based answers
- contextual prompt assembly for agents

## Legacy Routes Kept

These still work and remain useful:

- `GET /api/v1/observations/current`
- `GET /api/v1/observations/nearest`
- `GET /api/v1/forecast/48h`
- `GET /api/v1/forecast/weekly`
- `GET /api/v1/agro/latest`
- `GET /api/v1/dashboard/summary`

The canonical routes are the preferred surface for new frontend and ML integrations.

## Consumer Strategy

### Frontend
Prefer:
- `/api/v1/stations`
- `/api/v1/features/current`
- `/api/v1/context/location`

Why:
- fewer nested objects
- human-readable labels
- consistent metadata for cards, maps, and selectors

### ML
Prefer:
- `/api/v1/features/current`

Persist rows into:
- `stations`
- `observation_snapshots`
- `document_registry`

Recommended next step:
- schedule ingestion every 10 to 30 minutes into SQLite or Postgres

### LLM / Function Calling
Prefer:
- `/api/v1/context/location`
- `/api/v1/features/current?station_name=...`
- `/api/v1/documents/latest`

Why:
- deterministic structured retrieval for fresh numbers
- document metadata available for RAG and citations

### RAG
Use:
- `/api/v1/documents/latest` as the registry

Then:
1. download document or HTML source
2. extract text
3. chunk with metadata
4. store embeddings keyed by `document_id`, `document_type`, and date fields

## Design Rules

- Keep upstream SNET payloads behind the backend.
- Preserve stable IDs, but always include plain-language names.
- Prefer flattened rows for ML and nested rich objects for UI context bundles.
- Treat current numeric data as API/function-call data, not vector-search data.
- Treat forecasts and bulletins as document data, not primary numeric truth.
