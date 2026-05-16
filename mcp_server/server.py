"""
SATO-Agro MCP Server
====================
Model Context Protocol server that exposes the SATO-Agro backend
as MCP tools for any compatible LLM client (Claude Desktop, Cursor, etc.).

Run with:
    python mcp_server.py                     # stdio mode (for Claude Desktop)
    python mcp_server.py --transport sse     # SSE mode  (for web clients)

Requires the SATO-Agro backend running at SATO_AGRO_URL (default http://127.0.0.1:5000).
"""

from __future__ import annotations

import json
import os
import logging

import httpx
from mcp.server.fastmcp import FastMCP

# ── Config ─────────────────────────────────────────────────
BACKEND_URL = os.getenv("SATO_AGRO_URL", "http://127.0.0.1:5000")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sato-agro-mcp")

mcp = FastMCP(
    "sato-agro",
    instructions="SATO-Agro: early warning and prescriptive advisory system for smallholder agriculture in El Salvador",
)

# ── Helpers ────────────────────────────────────────────────

def _backend_error(
    *,
    method: str,
    path: str,
    status_code: int | None = None,
    error: str,
    backend_response: dict | None = None,
    raw_body: str | None = None,
) -> dict:
    payload = {
        "ok": False,
        "backend_url": BACKEND_URL,
        "method": method,
        "path": path,
        "status_code": status_code,
        "error": error,
    }
    if backend_response is not None:
        payload["backend_response"] = backend_response
    if raw_body:
        payload["raw_body_snippet"] = raw_body[:1000]
    return payload


def _response_json(response: httpx.Response) -> tuple[dict | None, str | None]:
    try:
        parsed = response.json()
    except ValueError:
        return None, response.text
    if not isinstance(parsed, dict):
        return None, response.text
    return parsed, None


def _backend_get(path: str, params: dict | None = None) -> dict:
    """GET request to SATO-Agro backend."""
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(f"{BACKEND_URL}{path}", params=params)
    except httpx.RequestError as exc:
        return _backend_error(method="GET", path=path, error=str(exc))

    parsed, raw_body = _response_json(response)
    if response.status_code >= 400:
        return _backend_error(
            method="GET",
            path=path,
            status_code=response.status_code,
            error="Backend returned an error response.",
            backend_response=parsed,
            raw_body=raw_body,
        )
    if parsed is None:
        return _backend_error(
            method="GET",
            path=path,
            status_code=response.status_code,
            error="Backend returned non-JSON or non-object JSON response.",
            raw_body=raw_body,
        )
    return parsed


def _backend_tool_call(tool_name: str, arguments: dict) -> dict:
    """POST to the generic /api/v1/ai/tools/call dispatcher."""
    path = "/api/v1/ai/tools/call"
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{BACKEND_URL}{path}",
                json={"tool_name": tool_name, "arguments": arguments},
            )
    except httpx.RequestError as exc:
        return _backend_error(method="POST", path=path, error=str(exc))

    parsed, raw_body = _response_json(response)
    if response.status_code >= 400:
        return _backend_error(
            method="POST",
            path=path,
            status_code=response.status_code,
            error="Backend returned an error response.",
            backend_response=parsed,
            raw_body=raw_body,
        )
    if parsed is None:
        return _backend_error(
            method="POST",
            path=path,
            status_code=response.status_code,
            error="Backend returned non-JSON or non-object JSON response.",
            raw_body=raw_body,
        )
    return parsed


def _tool_payload(
    backend_response: dict,
    *,
    route: str | None = None,
    backend_tool_name: str | None = None,
    arguments: dict | None = None,
) -> dict:
    if backend_response.get("ok") is False:
        payload = dict(backend_response)
        nested_response = payload.get("backend_response") if isinstance(payload.get("backend_response"), dict) else {}
        if "meta" not in payload and isinstance(nested_response.get("meta"), dict):
            payload["meta"] = nested_response["meta"]
        if "result" not in payload:
            if "result" in nested_response:
                payload["result"] = nested_response.get("result")
            elif "data" in nested_response:
                payload["result"] = nested_response.get("data")
        payload["arguments"] = arguments or {}
        if route:
            payload["route"] = route
        if backend_tool_name:
            payload["backend_tool_name"] = backend_tool_name
        return payload

    if backend_tool_name:
        result = backend_response.get("result")
        meta = backend_response.get("meta")
        error = backend_response.get("error")
    else:
        result = backend_response.get("data", backend_response)
        meta = backend_response.get("meta")
        error = None

    payload = {
        "ok": error is None,
        "backend_url": BACKEND_URL,
        "arguments": arguments or {},
        "result": result,
        "meta": meta,
    }
    if route:
        payload["route"] = route
    if backend_tool_name:
        payload["backend_tool_name"] = backend_tool_name
    if error:
        payload["error"] = error
    return payload


def _tool_json(
    backend_response: dict,
    *,
    route: str | None = None,
    backend_tool_name: str | None = None,
    arguments: dict | None = None,
) -> str:
    return json.dumps(
        _tool_payload(
            backend_response,
            route=route,
            backend_tool_name=backend_tool_name,
            arguments=arguments,
        ),
        ensure_ascii=False,
        indent=2,
    )


# ── MCP Tools ──────────────────────────────────────────────


@mcp.tool()
def get_weather_observed(lat: float, lon: float) -> str:
    """
    Get current observed weather for a location in El Salvador.
    Returns temperature (current/max/min), wind, rainfall, nearest stations.

    Args:
        lat: Latitude of the point (e.g. 13.69 for San Salvador)
        lon: Longitude of the point (e.g. -89.21 for San Salvador)
    """
    args = {"lat": lat, "lon": lon}
    result = _backend_tool_call("getWeatherObserved", args)
    return _tool_json(result, backend_tool_name="getWeatherObserved", arguments=args)


@mcp.tool()
def get_weather_forecast(lat: float, lon: float, target_date: str) -> str:
    """
    Get weather forecast for a location and target date.
    Returns temperature, rain, soil moisture, horizon classification.
    Dates beyond 16 days return a scenario instead of a precise forecast.

    Args:
        lat: Latitude of the point
        lon: Longitude of the point
        target_date: Target date in YYYY-MM-DD format (e.g. 2026-08-15)
    """
    args = {"lat": lat, "lon": lon, "target_date": target_date}
    result = _backend_get("/api/weather/forecast", args)
    return _tool_json(result, route="/api/weather/forecast", arguments=args)


@mcp.tool()
def get_geo_context(lat: float, lon: float, target_date: str | None = None) -> str:
    """
    Get territorial context: municipality, soil type, seasonal climate outlook.
    Useful for understanding the agricultural conditions of a location.

    Args:
        lat: Latitude of the point
        lon: Longitude of the point
        target_date: Optional YYYY-MM-DD date to select the correct seasonal outlook month
    """
    params = {"lat": lat, "lon": lon}
    if target_date:
        params["target_date"] = target_date
    result = _backend_get("/api/geo/context", params)
    return _tool_json(result, route="/api/geo/context", arguments=params)


@mcp.tool()
def get_risk_assessment(
    crop: str,
    sowing_date: str,
    lat: float,
    lon: float,
    target_date: str,
) -> str:
    """
    Get explainable crop risk assessment for maize or bean.
    Returns risk level, score, phenological phase, climate state,
    canicula watch status, actionable recommendations, and confidence.

    Args:
        crop: Crop type — either "maiz" or "frijol"
        sowing_date: Sowing date in YYYY-MM-DD format
        lat: Latitude of the plot
        lon: Longitude of the plot
        target_date: Target date for the assessment in YYYY-MM-DD format
    """
    args = {
        "crop": crop,
        "sowing_date": sowing_date,
        "lat": lat,
        "lon": lon,
        "target_date": target_date,
    }
    result = _backend_tool_call("getRiskAssessment", args)
    return _tool_json(result, backend_tool_name="getRiskAssessment", arguments=args)


@mcp.tool()
def get_official_context(target_date: str | None = None) -> str:
    """
    Get official 2026 canicula/drought context and seasonal explanation
    snippets from MARN/SNET official sources.

    Args:
        target_date: Optional YYYY-MM-DD date for the context window
    """
    args = {}
    if target_date:
        args["target_date"] = target_date
    result = _backend_tool_call("getOfficialContext", args)
    return _tool_json(result, backend_tool_name="getOfficialContext", arguments=args)


@mcp.tool()
def get_phenology_context(
    crop: str,
    sowing_date: str,
    target_date: str | None = None,
) -> str:
    """
    Estimate the phenological phase and susceptibility of a crop
    based on crop type, sowing date, and target date.

    Args:
        crop: Crop type — either "maiz" or "frijol"
        sowing_date: Sowing date in YYYY-MM-DD format
        target_date: Optional target date in YYYY-MM-DD format (defaults to today)
    """
    args = {"crop": crop, "sowing_date": sowing_date}
    if target_date:
        args["target_date"] = target_date
    result = _backend_tool_call("getPhenologyContext", args)
    return _tool_json(result, backend_tool_name="getPhenologyContext", arguments=args)


@mcp.tool()
def get_runtime_context(
    crop: str,
    sowing_date: str,
    lat: float,
    lon: float,
    target_date: str | None = None,
) -> str:
    """
    Build the complete runtime context bundle used by the assistant layer.
    Returns user inputs, UI state, plant state, observed weather, forecast,
    risk assessment, recommendations, official context, sources used, and source policy.

    Args:
        crop: Crop type — either "maiz" or "frijol"
        sowing_date: Sowing date in YYYY-MM-DD format
        lat: Latitude of the plot
        lon: Longitude of the plot
        target_date: Optional target date in YYYY-MM-DD format; defaults to today
    """
    args = {
        "crop": crop,
        "sowing_date": sowing_date,
        "lat": lat,
        "lon": lon,
    }
    if target_date:
        args["target_date"] = target_date
    result = _backend_tool_call("buildRuntimeContext", args)
    return _tool_json(result, backend_tool_name="buildRuntimeContext", arguments=args)


@mcp.tool()
def explain_recommendation(
    risk_assessment: dict,
    official_context: dict | None = None,
    audience: str = "productor",
) -> str:
    """
    Turn a structured risk assessment into a plain-language explanation
    suitable for a farmer or extension technician.

    Args:
        risk_assessment: The structured risk assessment object (from get_risk_assessment)
        official_context: Optional official context object
        audience: Target audience — "productor" or "tecnico"
    """
    payload = {"risk_assessment": risk_assessment, "audience": audience}
    if official_context is not None:
        payload["official_context"] = official_context
    result = _backend_tool_call(
        "explainRecommendation",
        payload,
    )
    return _tool_json(result, backend_tool_name="explainRecommendation", arguments=payload)


@mcp.tool()
def get_latest_documents() -> str:
    """
    Get the latest official documents used for RAG and citation workflows.
    Returns the canonical document registry from the backend compatibility route.
    """
    result = _backend_get("/api/v1/documents/latest")
    return _tool_json(result, route="/api/v1/documents/latest")


# ── MCP Resources ─────────────────────────────────────────


@mcp.resource("sato://health")
def resource_health() -> str:
    """Backend health and database connectivity status."""
    result = _backend_get("/health")
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.resource("sato://endpoints")
def resource_endpoints() -> str:
    """List of all available SATO-Agro backend endpoints."""
    result = _backend_get("/")
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Entry point ────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        transport = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "stdio"

    logger.info("Starting SATO-Agro MCP server (transport=%s, backend=%s)", transport, BACKEND_URL)
    mcp.run(transport=transport)
