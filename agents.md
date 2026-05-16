# AGENTS.md

## Purpose

This file is the working context for humans and AI agents contributing to this repository.

Read this first if you are going to:

- add backend features
- integrate a frontend
- connect an LLM agent
- build RAG ingestion
- extend data normalization
- improve risk or advisory logic
- persist product data in Supabase

This repo is no longer just a hackathon prototype. It already has a real backend contract, a manifest-aligned API surface, and a cloud database.

The main rule is still:

`do not bypass the normalized backend layer`

Use the backend as the source of truth instead of calling SNET/MARN, Open-Meteo, or Supabase directly from frontend or LLM workflows.

---

## Project Summary

**SATO-Agro** is an early warning and prescriptive advisory system for smallholder agriculture in El Salvador.

The current backend already does four important jobs:

- ingest public climate and territorial sources
- normalize them into stable JSON
- expose them through frontend-ready and LLM-ready contracts
- persist application data in Supabase PostgreSQL

The product goal is not only "show weather".

The product goal is:

- convert climate information into actionable agricultural guidance
- especially around canícula risk
- for maize and bean farmers

---

## Current State

Right now the repo is strongest in:

- backend normalization
- current observations and recent rainfall
- forecast and seasonal context assembly
- explainable rule-based crop risk assessment
- manifest-aligned LLM/runtime context
- Supabase schema and connectivity

This means the repo already contains:

- a reusable risk engine
- routes aligned to the updated manifest
- a generic AI tool surface
- scripts to apply and verify the cloud schema

---

## Repository Layout

Top-level files:

- `README.md`
  - project overview, run instructions, Supabase scripts
- `agents.md`
  - this file
- `docs/project/context.md`
  - original framing and product intent
- `docs/architecture/backend-hybrid-shape.md`
  - canonical backend shape for frontend + AI
- `docs/ai/llm-function-calling-spec.md`
  - legacy AI tool contract
- `docs/database/database-capture-plan.md`
  - storage planning
- `docs/database/database-schema.dbml`
  - database model

Backend:

- `backend/app.py`
  - Flask app factory, blueprint registration, DB pool startup
- `backend/config.py`
  - upstream URLs, cache TTLs, database env loading
- `backend/models/schemas.py`
  - dataclasses for response shapes and risk outputs
- `backend/services/`
  - raw upstream fetching and composition services
- `backend/normalizers/`
  - source-to-internal transformations and risk logic
- `backend/routes/`
  - HTTP endpoints
- `backend/scripts/`
  - migration and verification utilities
- `backend/migrations/`
  - SQL migrations for Supabase

Important route files:

- `backend/routes/weather.py`
  - `/api/weather/observed`, `/api/weather/forecast`
- `backend/routes/geo.py`
  - `/api/geo/context`
- `backend/routes/risk.py`
  - `/api/risk/assessment`
- `backend/routes/llm.py`
  - `/api/llm/context`, `/api/llm/explain`
- `backend/routes/ai_tools.py`
  - generic LLM tool manifest + dispatcher
- `backend/routes/canonical.py`
  - compatibility document endpoint plus shared helpers for AI tools

Important services:

- `backend/services/manifest_context.py`
  - orchestrates observed weather, forecast, geo context, and risk inputs
- `backend/services/open_meteo_forecast.py`
  - short-range forecast integration
- `backend/services/snet_rainfall.py`
  - rainfall 24h source
- `backend/services/snet_soil.py`
  - soil layer
- `backend/services/snet_climate_outlook.py`
  - monthly outlook layer
- `backend/services/snet_basins.py`
  - basin context
- `backend/services/snet_municipalities.py`
  - municipality lookup from coordinates
- `backend/services/database.py`
  - psycopg2 connection pool wrapper

Important normalizers:

- `backend/normalizers/risk.py`
  - rule-based risk engine and explainable outputs
- `backend/normalizers/rainfall.py`
  - rainfall 24h parser
- `backend/normalizers/soil.py`
  - soil context normalization
- `backend/normalizers/climate_outlook.py`
  - seasonal outlook normalization
- `backend/normalizers/basins.py`
  - basin normalization
- `backend/normalizers/municipalities.py`
  - municipality code/name normalization

Important scripts:

- `backend/scripts/apply_migrations.py`
  - applies SQL migrations to Supabase
- `backend/scripts/verify_database.py`
  - verifies public tables and enums in Supabase

---

## Architectural Rules

### 1. Respect the layered design

Use this path:

`route -> service -> normalizer -> schema -> response`

Do not:

- parse upstream HTML directly in routes
- fetch remote URLs from frontend code
- duplicate normalization across routes
- put risk logic directly inside HTTP handlers

### 2. Keep upstream fetches isolated

Each upstream source should have its own service file.

Service responsibilities:

- make HTTP requests
- return raw payloads or source-shaped payloads
- do only minimal source-specific extraction when unavoidable

Service files should not:

- build UI contracts
- flatten AI payloads
- decide business recommendations

### 3. Normalize once, reuse everywhere

If data needs to become frontend-friendly, AI-friendly, or risk-friendly, do it in normalizers or orchestration services, not ad hoc per route.

### 4. Prefer the manifest-aligned surface for new work

For new integrations, prefer:

- `/api/weather/observed`
- `/api/weather/forecast`
- `/api/geo/context`
- `/api/risk/assessment`
- `/api/llm/context`
- `/api/llm/explain`

The older `/api/v1/*` routes still exist and remain useful for compatibility, but they are no longer the best default for new product work.

### 5. Treat LLM tools as a first-class interface

The backend exposes:

- `GET /api/v1/ai/tools/manifest`
- `POST /api/v1/ai/tools/call`

If an assistant needs backend capabilities, start there before inventing a custom protocol.

### 6. Keep Supabase behind the backend

Frontend clients and agents should not treat Supabase tables as the primary API contract for climate or advisory features.

Supabase is for:

- user, farm, plot, crop, and advisory persistence
- future audit/history
- operational state

The backend remains the source of truth for:

- weather normalization
- territorial context
- risk assessment
- LLM runtime context

---

## Data Sources in Use

Current sources already wired:

- SNET temperature ArcGIS endpoint
- SNET wind ArcGIS endpoint
- SNET rainfall 24h endpoint
- SNET soil service
- SNET monthly climate outlook service
- SNET municipality boundary layer
- SNET basin data
- SNET station detail page
- SNET 48h forecast HTML page
- SNET weekly forecast PDF page
- SNET agro bulletin viewer page
- Open-Meteo short-range forecast

Important nuances:

- official station names are enriched from the public station detail page
- precise coordinates come from the wind layer when needed
- rainfall uses `valor_acumulado`
- municipality lookup is resolved from coordinates and then reused for soil context
- for horizons beyond Open-Meteo coverage, risk output is a scenario, not a precise forecast

---

## Canonical API Surface

### Manifest-aligned routes

- `GET /api/weather/observed`
  - observed weather bundle for a point
- `GET /api/weather/forecast`
  - forecast bundle for a point and target date
- `GET /api/geo/context`
  - municipality, basin, soil, and seasonal outlook context
- `GET /api/risk/assessment`
  - explainable risk output for crop, sowing date, and location
- `GET /api/llm/context`
  - runtime context contract for assistants
- `POST /api/llm/explain`
  - backend-generated plain-language explanation from structured context

### Compatibility routes

- `GET /api/v1/documents/latest`
- `GET /api/v1/ai/tools/manifest`
- `POST /api/v1/ai/tools/call`

Most older `/api/v1/*` weather, dashboard, and advisory convenience routes have been retired. Prefer the manifest-aligned routes for new development.

---

## LLM Tool Layer

The generic function-calling interface is:

- `GET /api/v1/ai/tools/manifest`
- `POST /api/v1/ai/tools/call`

Tool names now include both legacy and manifest-oriented operations, including:

- `getRiskAssessment`
- `getWeatherObserved`
- `getOfficialContext`
- `getPhenologyContext`
- `buildRuntimeContext`
- `explainRecommendation`
- `get_stations`
- `get_current_features`
- `get_latest_documents`
- `get_location_context`
- `get_agro_advisory`

Use cases:

- current-value questions
- location-aware weather questions
- explainable agronomic risk questions
- building assistant context before generation

Do not use embeddings as the source of truth for fresh numeric values.

---

## Risk and Advisory Model

The backend already includes a rule-based risk engine in `backend/normalizers/risk.py`.

It currently combines:

- crop type
- sowing date
- target date and horizon
- observed weather
- rainfall
- seasonal outlook
- soil modifier
- phenological stage assumptions

The engine is designed to be explainable and operational, not to pretend scientific precision it does not yet have.

When working on it:

- preserve transparent reasoning
- keep assumptions explicit in responses
- keep horizon semantics honest
- avoid burying critical overrides in route code

---

## Supabase

Supabase is already mounted into the project.

Current setup:

- `backend/.env` holds `DATABASE_URL`
- `backend/config.py` loads env vars
- `backend/services/database.py` manages the connection pool
- `backend/migrations/001_initial_schema.sql` creates the schema
- `backend/scripts/apply_migrations.py` applies migrations
- `backend/scripts/verify_database.py` verifies the mounted schema

Current public schema covers:

- `profiles`
- `user_preferences`
- `farms`
- `plots`
- `crop_types`
- `phenological_phases`
- `crop_cycles`
- `farmer_observations`
- `cycle_phase_history`
- `advisory_runs`
- `advisory_messages`
- `user_crop_interests`

Rules:

- do not hardcode credentials in code
- keep `.env` local and uncommitted
- use migrations for schema changes
- verify schema after changes

Recommended workflow:

1. edit or add SQL migration
2. run `python backend/scripts/apply_migrations.py`
3. run `python backend/scripts/verify_database.py`
4. run backend tests

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
- explainable risk scores

Recommended RAG flow:

1. use `/api/v1/documents/latest`
2. fetch the chosen document URL or HTML source
3. extract text
4. chunk with metadata
5. index by document id, type, issue time, and geography if available

---

## What Is Already Solved

The repo already solves:

- structured current weather retrieval
- station name enrichment
- nearest-station and location context lookup
- recent rainfall ingestion
- municipality resolution from coordinates
- soil and monthly outlook context assembly
- manifest-aligned risk assessment
- AI function-calling manifest + dispatcher
- Supabase connection and schema bootstrap

---

## What Is Still Open

These are still open areas:

- full PDF/text extraction pipeline for RAG
- persistent document chunk index
- ET0 or richer evapotranspiration logic
- richer forecast handling beyond 16 days
- persistence routes for profiles, farms, plots, and crop cycles
- advisory history writes into Supabase
- auth-aware RLS policies for real user traffic
- broader automated test coverage

High-value next steps are now:

- persist real product entities in Supabase
- write advisory runs and messages
- connect frontend onboarding to the DB model
- improve future-horizon risk inputs without hiding uncertainty

---

## Working Agreements for Contributors

### If you are building frontend

Prefer these routes first:

- `/api/weather/observed`
- `/api/weather/forecast`
- `/api/geo/context`
- `/api/risk/assessment`
- `/api/llm/context`

Use `/api/v1/documents/latest` only for document discovery and `/api/v1/ai/tools/*` only for tool-based assistant integrations.

### If you are building an LLM integration

Start with:

- `/api/v1/ai/tools/manifest`
- `/api/v1/ai/tools/call`

Then add RAG only for document interpretation, not for live structured values.

### If you are adding a new upstream source

Do this in order:

1. add service file
2. add or extend normalizer
3. add schema if needed
4. integrate into orchestration service if relevant
5. expose through route
6. expose through AI tool layer if useful
7. document it

### If you are adding persistence

Do this in order:

1. add or update migration
2. run migration script
3. verify schema
4. add DB service/repository access
5. expose through backend route or workflow
6. test end to end

### If you are adding business logic

Put decision logic in dedicated normalizers or orchestration services, not inside route handlers.

Examples:

- crop stage estimation
- drought risk score
- advisory generation
- explanation assembly

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
- `GET /api/weather/observed?lat=13.69&lon=-89.21`
- `GET /api/geo/context?lat=13.69&lon=-89.21&target_date=2026-08-15`
- `GET /api/risk/assessment?crop=maiz&sowing_date=2026-05-20&lat=13.69&lon=-89.21&target_date=2026-08-15`
- `GET /api/v1/ai/tools/manifest`
- `python backend/scripts/verify_database.py`

---

## Recommended Starting Reads

If you are new to the repo, read in this order:

1. `README.md`
2. `docs/project/context.md`
3. `docs/architecture/backend-hybrid-shape.md`
4. `docs/ai/llm-function-calling-spec.md`
5. this file

Then inspect:

1. `backend/app.py`
2. `backend/services/manifest_context.py`
3. `backend/routes/risk.py`
4. `backend/normalizers/risk.py`
5. `backend/routes/ai_tools.py`
6. `backend/services/database.py`

---

## Short Mental Model

Think of this repo as:

- a climate-data adapter layer
- plus an explainable risk engine
- plus an AI-ready tool layer
- plus a Supabase-backed application core

Right now:

- observed data is strong
- official and short-range context is strong
- LLM integration is strong
- Supabase is mounted
- persistence workflows are the next big product layer

If you build on top of the manifest-aligned backend surface and keep Supabase behind the backend, you will move faster and create less duplication.
