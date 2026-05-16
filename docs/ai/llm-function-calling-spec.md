# LLM Function Calling Spec

This backend exposes a compact tool layer for assistants at:

- `GET /api/v1/ai/tools/manifest`
- `POST /api/v1/ai/tools/call`

This layer is the preferred compatibility entrypoint for tool-based agents.

---

## Why This Layer Exists

- risk and phenology should come from the backend, not from model guessing
- official canícula context should be deterministic
- frontend, tool-calling agents, and backend logic should share one normalized source of truth
- assistants should ask for semantic results, not low-level climate fragments

---

## Tool Manifest

Use:

```http
GET /api/v1/ai/tools/manifest
```

It returns the currently supported tool names, descriptions, and input schemas.

The current manifest advertises 6 tools:

- `getRiskAssessment`
- `getWeatherObserved`
- `getOfficialContext`
- `getPhenologyContext`
- `buildRuntimeContext`
- `explainRecommendation`

Do not hardcode an older 10-tool manifest.

---

## Generic Tool Call Contract

Use:

```http
POST /api/v1/ai/tools/call
Content-Type: application/json
```

Body shape:

```json
{
  "tool_name": "getRiskAssessment",
  "arguments": {
    "crop": "maiz",
    "sowing_date": "2026-05-20",
    "lat": 13.69,
    "lon": -89.21,
    "target_date": "2026-08-15"
  }
}
```

Generic response shape:

```json
{
  "tool_name": "getRiskAssessment",
  "arguments": {
    "crop": "maiz",
    "sowing_date": "2026-05-20",
    "lat": 13.69,
    "lon": -89.21,
    "target_date": "2026-08-15"
  },
  "result": {},
  "meta": {
    "cached": true,
    "stale": false,
    "upstream_status": "ok",
    "fetched_at": "2026-05-16T18:39:34.102588+00:00"
  }
}
```

---

## Supported Tools

### `getRiskAssessment`

Purpose:

- calculate plant state, relevant climate, risk factors, score, level, confidence, and recommendations for a date

Arguments:

```json
{
  "crop": "maiz",
  "sowing_date": "2026-05-20",
  "lat": 13.69,
  "lon": -89.21,
  "target_date": "2026-08-15"
}
```

Use cases:

- answer current or future agroclimatic risk questions
- recompute risk for a slider date
- compare near-term vs seasonal scenario

---

### `getWeatherObserved`

Purpose:

- retrieve normalized observed weather for a location, including recent rainfall, temperature, wind, nearest stations, source metadata, and warnings

Arguments:

```json
{
  "lat": 13.69,
  "lon": -89.21
}
```

Use cases:

- answer current weather questions with backend-normalized SNET/MARN values
- provide observed context before a risk or advisory explanation
- avoid frontend or LLM clients calling raw SNET sources directly

---

### `getOfficialContext`

Purpose:

- retrieve official canícula, drought, or seasonal context for a target date

Arguments:

```json
{
  "target_date": "2026-08-15"
}
```

Optional location fields are also accepted:

```json
{
  "lat": 13.69,
  "lon": -89.21,
  "target_date": "2026-08-15"
}
```

Use cases:

- explain whether there is official canícula vigilance
- back seasonal explanations with official context
- refresh official snippets for another date

---

### `getPhenologyContext`

Purpose:

- estimate plant phase and susceptibility from crop plus sowing date

Arguments:

```json
{
  "crop": "maiz",
  "sowing_date": "2026-05-20",
  "target_date": "2026-08-15"
}
```

Use cases:

- answer phase-only questions
- estimate what stage the crop will be in at another date
- explain sensitivity without recalculating full climate risk

---

### `buildRuntimeContext`

Purpose:

- build the complete assistant runtime context bundle from the backend source of truth
- includes user inputs, plant state, observed weather, forecast/scenario context, risk assessment, recommendations, official context, assumptions, warnings, and source policy

Arguments:

```json
{
  "crop": "maiz",
  "sowing_date": "2026-05-20",
  "lat": 13.69,
  "lon": -89.21,
  "target_date": "2026-08-15",
  "visible_panel": "risk_summary"
}
```

Use cases:

- prepare a single, backend-composed context object before LLM generation
- avoid clients stitching weather, geo, risk, and official context differently
- power MCP or assistant integrations that need a complete context bundle

---

### `explainRecommendation`

Purpose:

- turn a structured risk assessment into a short explanation for producer or technician

Arguments:

```json
{
  "risk_assessment": {
    "risk_level": "alto",
    "risk_score": 0.82
  },
  "official_context": {
    "canicula_2026_watch": true
  },
  "audience": "productor"
}
```

Use cases:

- simplify a backend risk result into producer language
- power “explain this” buttons in the UI

---

## Recommended Orchestration

For an assistant:

1. If the user asks about current or future crop risk:
   - call `getRiskAssessment`
2. If the user asks about current observed weather values:
   - call `getWeatherObserved`
3. If the user asks whether canícula or seasonal dryness is officially expected:
   - call `getOfficialContext`
4. If the user asks only about stage, flowering, pod formation, or sensitivity:
   - call `getPhenologyContext`
5. If the assistant needs one complete generation context:
   - call `buildRuntimeContext`
6. If the backend result already exists and the user wants a simpler explanation:
   - call `explainRecommendation`

---

## Design Guidance

- use tool calls for fresh structured risk and phenology
- use `/api/v1/documents/latest` separately when you need document discovery for RAG
- do not rely on embeddings for current numeric climate values or live risk state
- do not build new assistants around older legacy tools like `get_current_features`, `get_location_context`, or `get_agro_advisory`
- use `buildRuntimeContext` when an assistant needs the complete backend-composed runtime contract

---

## MCP Notes

The MCP server exposes snake_case tools that map to these backend tool names or manifest routes.

Important MCP response shape:

```json
{
  "ok": true,
  "backend_tool_name": "buildRuntimeContext",
  "arguments": {},
  "result": {},
  "meta": {}
}
```

On backend or validation errors, MCP tools return `ok: false` with `error`, `status_code`, and any backend `meta` preserved when available. MCP clients should inspect `ok` instead of assuming every tool response is successful.
