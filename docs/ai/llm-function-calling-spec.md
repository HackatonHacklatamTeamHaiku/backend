# LLM Function Calling Spec

This backend exposes a simple tool layer for an LLM at:

- `GET /api/v1/ai/tools/manifest`
- `POST /api/v1/ai/tools/call`

The tool layer sits on top of the canonical backend shape and is meant to be the preferred entrypoint for an assistant.

## Why This Layer Exists

- current numeric weather data should be fetched deterministically
- station names should be plain-language, not only numeric ids
- the frontend and the LLM should read from the same normalized truth
- forecast and bulletin documents should be discoverable for RAG

## Tool Manifest

Use:

```http
GET /api/v1/ai/tools/manifest
```

It returns the currently supported tool names, descriptions, and input schemas.

## Generic Tool Call Contract

Use:

```http
POST /api/v1/ai/tools/call
Content-Type: application/json
```

Body:

```json
{
  "tool_name": "get_location_context",
  "arguments": {
    "lat": 13.69,
    "lon": -89.21
  }
}
```

Response shape:

```json
{
  "tool_name": "get_location_context",
  "arguments": {
    "lat": 13.69,
    "lon": -89.21
  },
  "result": {},
  "meta": {
    "cached": true,
    "stale": false,
    "upstream_status": "ok",
    "fetched_at": "2026-05-16T03:26:59.206519+00:00"
  }
}
```

## Supported Tools

### `get_stations`
Look up stations by plain-language name or id.

Arguments:

```json
{
  "station_id": 4,
  "station_name": "Ilopango"
}
```

Use cases:
- resolve a station before asking for weather
- build station selectors
- map human names to canonical ids

### `get_current_features`
Get flattened current observation rows.

Arguments:

```json
{
  "station_name": "Ilopango"
}
```

or:

```json
{
  "lat": 13.69,
  "lon": -89.21
}
```

Returns fields like:
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

Use cases:
- current weather answers
- location-based weather lookup
- structured tool data for prompts

### `get_latest_documents`
Get latest forecast and bulletin documents for RAG.

Optional argument:

```json
{
  "document_type": "agro_bulletin_pdf"
}
```

Supported values:
- `forecast_48h`
- `weekly_forecast_pdf`
- `agro_bulletin_pdf`

Use cases:
- choose which documents to ingest into RAG
- cite latest forecast sources
- fetch bulletin URLs before OCR or chunking

### `get_location_context`
Get one full context bundle for a target location.

Arguments:

```json
{
  "lat": 13.69,
  "lon": -89.21
}
```

Returns:
- `location`
- `station`
- `observation`
- `features`
- `documents`
- `meta`

Use cases:
- one-shot assistant answers
- frontend summary cards
- prompt assembly with live data and documents together

## Recommended Orchestration

For an LLM assistant:

1. If the user asks for current values:
   - call `get_current_features` or `get_location_context`
2. If the user asks for latest bulletin or forecast interpretation:
   - call `get_latest_documents`
   - fetch and chunk the selected document in RAG
3. If the user asks for both current conditions and advisory context:
   - call `get_location_context`
   - then use `documents` for retrieval

## Design Guidance

- Use function calls for fresh structured data.
- Use RAG for PDFs and narrative forecast text.
- Do not rely on embeddings for current numeric weather values.
- Keep the tool layer as the LLM’s source of truth for live state.
