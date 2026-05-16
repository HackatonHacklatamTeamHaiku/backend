# AGENTS.md

## Purpose

This file is the working context for humans and AI agents contributing to this repository.

Read this first if you are going to:

- add backend features
- integrate a frontend
- connect an LLM agent
- build RAG ingestion
- extend data normalization
- improve advisory logic for crops

This repo is a hackathon codebase, but it already has a real backend shape. The main rule is:

`do not bypass the normalized backend layer`

Use the backend as the source of truth instead of calling SNET/MARN directly from frontend or LLM workflows.

---

## Project Summary

**SATO-Agro** is an early warning and prescriptive advisory system for smallholder agriculture in El Salvador.

The current focus is:

- ingest public SNET/MARN climate and forecast sources
- normalize them into stable JSON
- make them usable by:
  - frontend apps
  - LLM function-calling
  - RAG pipelines

The problem we are solving is not only "show weather data".

The real product goal is:

- convert climate information into actionable agricultural guidance
- especially around canícula risk
- for maize and bean farmers

Right now the repo is strongest in:

- backend normalization
- current observations
- official forecast retrieval
- AI-ready tool surface

It is not yet a full agronomic decision engine.

---

## Current Product Direction

The architecture is now optimized for:

- `frontend + LLM`

Not for:

- training a custom ML model from scratch

That means:

- `function calling` is the primary path for fresh structured data
- `RAG` is the primary path for bulletins, forecast text, and PDFs
- `rule-based advisory logic` is the most realistic next step for crop recommendations

If someone wants to add "prediction", the safe framing is:

- estimate crop stage
- combine with official forecast context
- output a risk/advisory

Do not claim scientifically rigorous climate or plant-growth prediction unless a real validated model is added.

---

## Repository Layout

Top-level files:

- `README.md`
  - project overview and quick start
- `context.md`
  - original hackathon framing and product intent
- `snet_api_roadmap.md`
  - verified source roadmap
- `snet_raw_endpoints.md`
  - raw endpoint reference
- `snet_latest_2026_endpoints.md`
  - latest/current verified source list
- `backend_hybrid_shape.md`
  - canonical backend shape for frontend + AI
- `llm_function_calling_spec.md`
  - tool contract for LLM integration

Backend:

- `backend/app.py`
  - Flask app factory and blueprint registration
- `backend/config.py`
  - upstream URLs, cache TTLs, HTTP settings
- `backend/models/schemas.py`
  - dataclasses for all canonical response shapes
- `backend/services/`
  - fetch raw upstream data only
- `backend/normalizers/`
  - transform raw source payloads into internal objects
- `backend/routes/`
  - HTTP endpoints
- `backend/utils/`
  - cache, time, geo, http helpers

Important route files:

- `backend/routes/observations.py`
  - legacy observation endpoints
- `backend/routes/forecasts.py`
  - 48h + weekly forecast endpoints
- `backend/routes/agro.py`
  - agro bulletin endpoint
- `backend/routes/dashboard.py`
  - original dashboard summary endpoint
- `backend/routes/canonical.py`
  - canonical routes for frontend and AI consumers
- `backend/routes/ai_tools.py`
  - LLM-facing function-calling routes

Important normalizers:

- `backend/normalizers/observations.py`
  - merge temp + wind, attach station metadata
- `backend/normalizers/forecasts.py`
  - parse 48h forecast HTML
- `backend/normalizers/agro.py`
  - normalize PDF metadata
- `backend/normalizers/canonical.py`
  - build flattened station/feature/document records

Important services:

- `backend/services/snet_temperature.py`
- `backend/services/snet_wind.py`
- `backend/services/snet_station_metadata.py`
- `backend/services/snet_forecast_48h.py`
- `backend/services/snet_weekly_pdf.py`
- `backend/services/snet_agro_pdf.py`

---

## Architectural Rules

### 1. Respect the layered design

Use this path:

`route -> service -> normalizer -> schema -> response`

Do not:

- parse upstream HTML directly in routes
- fetch remote URLs from frontend code
- duplicate normalization in multiple routes

### 2. Keep upstream fetches isolated

Each upstream source should have its own service file.

Service responsibilities:

- make HTTP requests
- return raw payloads
- do minimal source-specific extraction if absolutely necessary

Service files should not:

- build UI-friendly output
- flatten for ML/LLM
- decide crop logic

### 3. Normalize once, reuse everywhere

If data needs to become AI-friendly or frontend-friendly, do that in normalizers and canonical builders, not ad hoc in every route.

### 4. Use the canonical layer for new work

For new integrations, prefer:

- `/api/v1/stations`
- `/api/v1/features/current`
- `/api/v1/documents/latest`
- `/api/v1/context/location`

The older routes still work, but they are not the preferred surface for new agents or new UI work.

### 5. Treat LLM tools as a first-class interface

The backend already exposes:

- `GET /api/v1/ai/tools/manifest`
- `POST /api/v1/ai/tools/call`

Any agent or assistant integration should start there before inventing a custom protocol.

---

## Data Sources in Use

Current public sources already wired:

- SNET temperature ArcGIS endpoint
- SNET wind ArcGIS endpoint
- SNET station detail page for human-readable station names
- SNET 48h forecast HTML page
- SNET weekly forecast PDF page
- SNET agro bulletin viewer page

Important nuance:

- official station names are enriched from the public station detail page
- precise coordinates come from the wind layer because the temperature layer may be coarse/rounded

This matters for:

- nearest station lookup
- frontend map positioning
- LLM answers that mention places by name

---

## Canonical API Surface

### `GET /api/v1/stations`

Use for:

- station lists
- station selectors
- map marker metadata
- plain-language station lookup

Returns station identity only, not nested weather payloads.

### `GET /api/v1/features/current`

Use for:

- frontend cards/tables that want flat numeric values
- LLM tool outputs for current weather
- analytics-style consumption

Important fields include:

- `station_name`
- `observed_at`
- `observed_at_local`
- `temperature_current_c`
- `temperature_max_c`
- `temperature_min_c`
- `temperature_diurnal_range_c`
- `wind_direction_deg`
- `wind_speed`
- `observation_age_minutes`
- `is_complete`

### `GET /api/v1/documents/latest`

Use for:

- RAG document registry
- latest bulletin/forecast links
- document metadata display

Current document types:

- `forecast_48h`
- `weekly_forecast_pdf`
- `agro_bulletin_pdf`

### `GET /api/v1/context/location?lat=&lon=`

Use for:

- one-shot frontend summary
- one-shot LLM context bundle
- location-based advisory pipelines

This returns:

- requested location
- nearest station
- nested observation
- flattened feature row
- latest documents
- response metadata

---

## LLM Tool Layer

The generic function-calling interface is:

- `GET /api/v1/ai/tools/manifest`
- `POST /api/v1/ai/tools/call`

Current tool names:

- `get_stations`
- `get_current_features`
- `get_latest_documents`
- `get_location_context`

Use cases:

- current-value questions
- location-aware weather questions
- selecting latest source documents before RAG

Recommended LLM orchestration:

1. If the question is about current values:
   - call `get_current_features` or `get_location_context`
2. If the question is about bulletin meaning or official forecast interpretation:
   - call `get_latest_documents`
   - then retrieve/chunk the selected document in RAG
3. If the question needs both current status and official outlook:
   - call `get_location_context`
   - then use returned documents for retrieval

Do not use embeddings as the source of truth for fresh numeric weather values.

---

## RAG Guidance

RAG is appropriate here for:

- agro bulletins
- weekly forecast PDFs
- 48h forecast narrative text

RAG is not the primary interface for:

- current station temperature
- current wind
- nearest station lookup
- live structured observations

Recommended RAG flow:

1. use `/api/v1/documents/latest`
2. fetch the chosen document URL or HTML source
3. extract text
4. chunk with metadata
5. index by:
   - `document_id`
   - `document_type`
   - `issued_at`
   - `last_modified`
   - geography if available

---

## What Is Already Solved

The repo already solves:

- structured current weather retrieval
- station name enrichment
- location-to-nearest-station lookup
- latest forecast document discovery
- latest agro bulletin discovery
- AI function-calling manifest + wrapper
- canonical backend shape for frontend and AI reuse

---

## What Is Not Solved Yet

These are still open areas:

- real document text extraction pipeline for PDFs
- stored vector index / RAG implementation
- crop-stage estimation engine
- agronomic advisory endpoint
- rules for maize and bean phenology/risk
- user profile / farm profile / sowing metadata persistence
- historical timeseries store
- tests beyond basic runtime verification

If you are adding product intelligence, the highest-value next layer is probably:

- `/api/v1/agro/advisory`

Input:

- crop
- sowing date
- location

Output:

- estimated current stage
- next critical stage window
- climate risk level
- explanation
- recommended action

That would fit the current architecture very well.

---

## Working Agreements for Contributors

### If you are building frontend

Prefer these routes first:

- `/api/v1/context/location`
- `/api/v1/features/current`
- `/api/v1/stations`
- `/api/v1/documents/latest`

Do not parse nested legacy payloads if a canonical route already gives you the cleaner data.

### If you are building an LLM integration

Start with:

- `/api/v1/ai/tools/manifest`
- `/api/v1/ai/tools/call`

Then add RAG only for document interpretation.

### If you are adding a new upstream source

Do this in order:

1. add service file
2. add or extend normalizer
3. add schema if needed
4. expose through canonical route if relevant
5. expose through AI tool layer if useful for assistants
6. document it in the relevant `.md` files

### If you are adding business logic

Put decision logic in a dedicated normalizer/service layer, not inside the route handler.

Examples:

- crop stage estimation
- drought risk score
- advisory generation

---

## Code and Repo Hygiene

- repo root is the git repo
- `backend/` is the Flask app
- do not commit `.venv/`
- do not add cached or generated files unless they are intentional artifacts
- keep response shapes stable once exposed
- preserve backward compatibility when possible

If you need a new response shape:

- prefer adding a canonical route instead of breaking an existing route

---

## Local Run

From the project root:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Base URL:

```text
http://127.0.0.1:5000
```

Useful checks:

- `GET /health`
- `GET /api/v1/stations`
- `GET /api/v1/features/current`
- `GET /api/v1/documents/latest`
- `GET /api/v1/ai/tools/manifest`

---

## Recommended Starting Reads

If you are new to the repo, read in this order:

1. `README.md`
2. `context.md`
3. `backend_hybrid_shape.md`
4. `llm_function_calling_spec.md`
5. this file

Then inspect:

1. `backend/app.py`
2. `backend/routes/canonical.py`
3. `backend/routes/ai_tools.py`
4. `backend/normalizers/canonical.py`
5. `backend/normalizers/observations.py`

---

## Short Mental Model

Think of this repo as:

- a climate-data adapter layer
- plus an AI-ready tool layer
- plus the base for an agronomic advisory product

Right now:

- current data is strong
- official forecast retrieval is strong
- LLM integration path is strong
- crop intelligence is the next frontier

If you build on top of the canonical backend and AI tool surface, you will move faster and create less duplication.
