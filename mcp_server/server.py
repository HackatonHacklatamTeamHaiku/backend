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
    description="SATO-Agro: early warning and prescriptive advisory system for smallholder agriculture in El Salvador",
)

# ── Helpers ────────────────────────────────────────────────

def _backend_get(path: str, params: dict | None = None) -> dict:
    """GET request to SATO-Agro backend."""
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{BACKEND_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()


def _backend_tool_call(tool_name: str, arguments: dict) -> dict:
    """POST to the generic /api/v1/ai/tools/call dispatcher."""
    with httpx.Client(timeout=30) as client:
        r = client.post(
            f"{BACKEND_URL}/api/v1/ai/tools/call",
            json={"tool_name": tool_name, "arguments": arguments},
        )
        r.raise_for_status()
        return r.json()


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
    result = _backend_get("/api/weather/observed", {"lat": lat, "lon": lon})
    return json.dumps(result, ensure_ascii=False, indent=2)


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
    result = _backend_get(
        "/api/weather/forecast",
        {"lat": lat, "lon": lon, "target_date": target_date},
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


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
    return json.dumps(result, ensure_ascii=False, indent=2)


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
    result = _backend_get(
        "/api/risk/assessment",
        {
            "crop": crop,
            "sowing_date": sowing_date,
            "lat": lat,
            "lon": lon,
            "target_date": target_date,
        },
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


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
    return json.dumps(result.get("result", result), ensure_ascii=False, indent=2)


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
    return json.dumps(result.get("result", result), ensure_ascii=False, indent=2)


@mcp.tool()
def build_runtime_context(
    crop: str,
    sowing_date: str,
    lat: float,
    lon: float,
    target_date: str,
) -> str:
    """
    Build a complete runtime context bundle for AI generation.
    Assembles observed weather, forecast, geo context, phenology,
    and official seasonal context into one payload.

    Args:
        crop: Crop type — either "maiz" or "frijol"
        sowing_date: Sowing date in YYYY-MM-DD format
        lat: Latitude of the plot
        lon: Longitude of the plot
        target_date: Target date in YYYY-MM-DD format
    """
    result = _backend_tool_call(
        "buildRuntimeContext",
        {
            "crop": crop,
            "sowing_date": sowing_date,
            "lat": lat,
            "lon": lon,
            "target_date": target_date,
        },
    )
    return json.dumps(result.get("result", result), ensure_ascii=False, indent=2)


@mcp.tool()
def explain_recommendation(
    risk_assessment: dict,
    audience: str = "productor",
) -> str:
    """
    Turn a structured risk assessment into a plain-language explanation
    suitable for a farmer or extension technician.

    Args:
        risk_assessment: The structured risk assessment object (from get_risk_assessment)
        audience: Target audience — "productor" or "tecnico"
    """
    result = _backend_tool_call(
        "explainRecommendation",
        {"risk_assessment": risk_assessment, "audience": audience},
    )
    return json.dumps(result.get("result", result), ensure_ascii=False, indent=2)


@mcp.tool()
def get_stations(station_name: str | None = None) -> str:
    """
    List weather stations in El Salvador.
    Optionally filter by name (case-insensitive partial match).

    Args:
        station_name: Optional station name to search for (e.g. "Ilopango", "UES")
    """
    args = {}
    if station_name:
        args["station_name"] = station_name
    result = _backend_tool_call("get_stations", args)
    return json.dumps(result.get("result", result), ensure_ascii=False, indent=2)


@mcp.tool()
def get_current_features(lat: float, lon: float) -> str:
    """
    Get current observation features for the nearest weather station
    to a location. Returns temperature, wind, observation age, etc.

    Args:
        lat: Latitude of the point
        lon: Longitude of the point
    """
    result = _backend_tool_call(
        "get_current_features", {"lat": lat, "lon": lon}
    )
    return json.dumps(result.get("result", result), ensure_ascii=False, indent=2)


@mcp.tool()
def get_latest_documents(document_type: str | None = None) -> str:
    """
    Get latest official documents (48h forecast, weekly PDF, agro bulletin).
    Useful for RAG and citations.

    Args:
        document_type: Optional filter — "forecast_48h", "weekly_forecast_pdf", or "agro_bulletin_pdf"
    """
    args = {}
    if document_type:
        args["document_type"] = document_type
    result = _backend_tool_call("get_latest_documents", args)
    return json.dumps(result.get("result", result), ensure_ascii=False, indent=2)


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
