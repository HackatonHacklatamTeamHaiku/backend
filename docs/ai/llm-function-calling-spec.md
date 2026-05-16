# LLM Function Calling Spec

This backend exposes a compact tool layer for assistants at:

- `POST /api/llm/chat`
- `GET /api/v1/ai/tools/manifest`
- `POST /api/v1/ai/tools/call`

`/api/llm/chat` is the preferred backend-managed LLM entrypoint.
The `/api/v1/ai/tools/*` layer remains the preferred compatibility entrypoint for external tool-based agents, MCP clients, or custom orchestrators.

---

## Why This Layer Exists

- risk and phenology should come from the backend, not from model guessing
- official canícula context should be deterministic
- frontend, tool-calling agents, and backend logic should share one normalized source of truth
- assistants should ask for semantic results, not low-level climate fragments
- the backend should own the tool loop when the product wants one stable chat contract

---

## Backend-managed Chat

Use:

```http
POST /api/llm/chat
Content-Type: application/json
```

Body shape:

```json
{
  "message": "como va mi maiz",
  "model": "openai/gpt-5.4-pro",
  "crop": "maiz",
  "sowing_date": "2026-05-10",
  "lat": 13.8,
  "lon": -89.1833,
  "target_date": "2026-05-16",
  "conversation": [
    { "role": "user", "content": "sembré el 10 de mayo" },
    { "role": "assistant", "content": "Entendido." }
  ]
}
```

Notes:

- `message` is required
- `model` is optional and may be selected by frontend
- if frontend sends a model, the backend uses it first
- the backend always keeps `mistralai/mistral-medium-3.1` as fallback through OpenRouter routing
- the backend injects the current `runtime_context` and runs the semantic tool loop itself

Response shape:

```json
{
  "data": {
    "reply": "Tu maiz va con riesgo preventivo alto...",
    "runtime_context": {},
    "tool_calls": [
      {
        "tool_name": "getRiskAssessment",
        "arguments": {},
        "status": 200,
        "meta": {}
      }
    ],
    "model": "openai/gpt-5.4-pro",
    "requested_model": "openai/gpt-5.4-pro",
    "routing_models": [
      "openai/gpt-5.4-pro",
      "mistralai/mistral-medium-3.1"
    ],
    "finish_reason": "stop",
    "openrouter_metadata": {}
  },
  "meta": {
    "cached": false,
    "stale": false,
    "upstream_status": "ok",
    "fetched_at": "2026-05-16T18:39:34.102588+00:00"
  }
}
```

Use cases:

- product chat UI
- assistant panel inside frontend
- model switching from UI without rewriting tool orchestration

---

## Tool Manifest

Use:

```http
GET /api/v1/ai/tools/manifest
```

It returns the currently supported tool names, descriptions, and input schemas.

The current manifest advertises 4 semantic tools:

- `getRiskAssessment`
- `getOfficialContext`
- `getPhenologyContext`
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

For a backend-managed assistant:

1. call `POST /api/llm/chat`
2. let the backend decide whether to use `getRiskAssessment`, `getOfficialContext`, `getPhenologyContext`, or `explainRecommendation`
3. render `data.reply`
4. optionally log `tool_calls`, `model`, and `routing_models` for debugging

For an external tool-calling assistant:

1. If the user asks about current or future crop risk:
   - call `getRiskAssessment`
2. If the user asks whether canícula or seasonal dryness is officially expected:
   - call `getOfficialContext`
3. If the user asks only about stage, flowering, pod formation, or sensitivity:
   - call `getPhenologyContext`
4. If the backend result already exists and the user wants a simpler explanation:
   - call `explainRecommendation`

---

## Design Guidance

- use `/api/llm/chat` when the frontend wants one simple conversational contract
- use tool calls for fresh structured risk and phenology
- use `/api/v1/documents/latest` separately when you need document discovery for RAG
- do not rely on embeddings for current numeric climate values or live risk state
- do not build new assistants around older tools like `get_current_features`, `get_location_context`, `get_agro_advisory`, or `buildRuntimeContext`
