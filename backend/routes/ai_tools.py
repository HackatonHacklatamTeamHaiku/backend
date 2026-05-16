"""
LLM-facing tool routes built on top of the canonical backend layer.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from models.schemas import CanonicalLocationContext, DocumentRecord, Location, ResponseMeta, to_dict
from normalizers.canonical import feature_row_from_observation, station_from_observation
from routes.agro import build_advisory_payload
from services.manifest_context import (
    build_runtime_llm_context,
    explain_recommendation,
    get_official_context,
    get_phenology_context,
    get_risk_assessment,
)
from routes.canonical import (
    _build_meta,
    _get_agro_document,
    _get_forecast_document,
    _get_observations,
    _get_weekly_document,
)
from utils.geo import find_nearest
from utils.time import now_utc_iso

logger = logging.getLogger(__name__)

bp = Blueprint("ai_tools", __name__, url_prefix="/api/v1/ai/tools")


def _filter_rows(rows: list[dict], station_id: int | None = None, station_name: str | None = None) -> list[dict]:
    """Filter station-shaped rows by id and/or a case-insensitive name query."""
    filtered = rows
    if station_id is not None:
        filtered = [row for row in filtered if row.get("station_id") == station_id]
    if station_name:
        search = station_name.strip().lower()
        filtered = [
            row for row in filtered
            if search in (row.get("station_name") or "").lower()
            or search in (row.get("station_code") or "").lower()
            or search in (row.get("station_label") or "").lower()
        ]
    return filtered


def _station_records() -> tuple[list[dict], dict]:
    observations, stale, fetched_at = _get_observations()
    records = [to_dict(station_from_observation(obs)) for obs in observations]
    meta = _build_meta(
        cached=bool(records),
        stale=stale,
        upstream_status="failed" if stale else "ok",
        fetched_at=fetched_at,
    )
    return records, meta


def _feature_records() -> tuple[list[dict], dict]:
    observations, stale, fetched_at = _get_observations()
    rows = [to_dict(feature_row_from_observation(obs)) for obs in observations]
    meta = _build_meta(
        cached=bool(rows),
        stale=stale,
        upstream_status="failed" if stale else "ok",
        fetched_at=fetched_at,
    )
    return rows, meta


def _document_records() -> tuple[list[dict], dict]:
    forecast_doc, forecast_stale, forecast_fetched_at = _get_forecast_document()
    weekly_doc, weekly_stale, weekly_fetched_at = _get_weekly_document()
    agro_doc, agro_stale, agro_fetched_at = _get_agro_document()

    documents = [doc for doc in (forecast_doc, weekly_doc, agro_doc) if doc is not None]
    any_stale = forecast_stale or weekly_stale or agro_stale
    fetched_at = max(
        [ts for ts in (forecast_fetched_at, weekly_fetched_at, agro_fetched_at) if ts],
        default=now_utc_iso(),
    )
    meta = _build_meta(
        cached=bool(documents),
        stale=any_stale,
        upstream_status="degraded" if any_stale else "ok",
        fetched_at=fetched_at,
    )
    return documents, meta


def _location_context(lat: float, lon: float) -> tuple[dict, dict]:
    observations, obs_meta = _feature_records()
    nearest = find_nearest(lat, lon, observations) if observations else None

    documents, docs_meta = _document_records()
    fetched_at = max(
        [ts for ts in (obs_meta.get("fetched_at"), docs_meta.get("fetched_at")) if ts],
        default=now_utc_iso(),
    )
    any_stale = obs_meta.get("stale", False) or docs_meta.get("stale", False)
    upstream_status = "degraded" if any_stale else "ok"

    raw_observations, _, _ = _get_observations()
    raw_nearest = find_nearest(lat, lon, raw_observations) if raw_observations else None

    payload = CanonicalLocationContext(
        location=Location(lat=lat, lon=lon),
        station=station_from_observation(raw_nearest) if raw_nearest else None,
        observation=raw_nearest,
        features=feature_row_from_observation(raw_nearest) if raw_nearest else None,
        documents=[DocumentRecord(**doc) for doc in documents],
        meta=ResponseMeta(
            cached=True,
            stale=any_stale,
            upstream_status=upstream_status,
            fetched_at=fetched_at,
        ),
    )
    return to_dict(payload), to_dict(payload.meta)


def _call_tool(tool_name: str, arguments: dict) -> tuple[dict, int]:
    """Dispatch one AI tool call and return a JSON-safe payload + status code."""
    if tool_name == "get_stations":
        records, meta = _station_records()
        result = _filter_rows(
            records,
            station_id=arguments.get("station_id"),
            station_name=arguments.get("station_name"),
        )
        return {"tool_name": tool_name, "arguments": arguments, "result": result, "meta": meta}, 200

    if tool_name == "get_current_features":
        records, meta = _feature_records()
        lat = arguments.get("lat")
        lon = arguments.get("lon")
        if lat is not None and lon is not None and records:
            nearest = find_nearest(lat, lon, records)
            records = [nearest] if nearest else []
        result = _filter_rows(
            records,
            station_id=arguments.get("station_id"),
            station_name=arguments.get("station_name"),
        )
        return {"tool_name": tool_name, "arguments": arguments, "result": result, "meta": meta}, 200

    if tool_name == "get_latest_documents":
        records, meta = _document_records()
        document_type = arguments.get("document_type")
        if document_type:
            records = [doc for doc in records if doc.get("document_type") == document_type]
        return {"tool_name": tool_name, "arguments": arguments, "result": records, "meta": meta}, 200

    if tool_name == "get_location_context":
        lat = arguments.get("lat")
        lon = arguments.get("lon")
        if lat is None or lon is None:
            return {
                "tool_name": tool_name,
                "arguments": arguments,
                "error": "lat and lon are required",
            }, 400
        result, meta = _location_context(float(lat), float(lon))
        return {"tool_name": tool_name, "arguments": arguments, "result": result, "meta": meta}, 200

    if tool_name == "get_agro_advisory":
        result, meta, status = build_advisory_payload(arguments)
        body = {"tool_name": tool_name, "arguments": arguments, "result": result, "meta": meta}
        if status >= 400:
            body["error"] = result.get("error")
        return body, status

    if tool_name == "getRiskAssessment":
        result, meta, status = get_risk_assessment(arguments)
        body = {"tool_name": tool_name, "arguments": arguments, "result": result, "meta": meta}
        if status >= 400:
            body["error"] = result.get("error")
        return body, status

    if tool_name == "getOfficialContext":
        target_date = arguments.get("target_date")
        if not target_date:
            return {"tool_name": tool_name, "arguments": arguments, "error": "target_date is required"}, 400
        from datetime import datetime

        result = get_official_context(datetime.strptime(target_date, "%Y-%m-%d").date())
        return {"tool_name": tool_name, "arguments": arguments, "result": result, "meta": {"cached": True, "stale": False, "upstream_status": "ok", "fetched_at": now_utc_iso()}}, 200

    if tool_name == "getPhenologyContext":
        crop = arguments.get("crop")
        sowing_date = arguments.get("sowing_date")
        if not crop or not sowing_date:
            return {"tool_name": tool_name, "arguments": arguments, "error": "crop and sowing_date are required"}, 400
        result = get_phenology_context(crop, sowing_date, arguments.get("target_date"))
        return {"tool_name": tool_name, "arguments": arguments, "result": result, "meta": {"cached": True, "stale": False, "upstream_status": "ok", "fetched_at": now_utc_iso()}}, 200

    if tool_name == "buildRuntimeContext":
        result, meta, status = build_runtime_llm_context(arguments)
        body = {"tool_name": tool_name, "arguments": arguments, "result": result, "meta": meta}
        if status >= 400:
            body["error"] = result.get("error")
        return body, status

    if tool_name == "explainRecommendation":
        result = explain_recommendation(arguments)
        return {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "meta": {"cached": True, "stale": False, "upstream_status": "ok", "fetched_at": now_utc_iso()},
        }, 200

    return {"error": f"Unknown tool_name: {tool_name}"}, 404


@bp.route("/manifest")
def manifest():
    """Return a function-calling manifest for LLM clients."""
    return jsonify({
        "provider": "sato-agro-backend",
        "version": "1.0.0",
        "tools": [
            {
                "name": "get_stations",
                "description": "Look up canonical weather stations by id or plain-language name.",
                "method": "POST",
                "endpoint": "/api/v1/ai/tools/call",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "station_id": {"type": "integer"},
                        "station_name": {"type": "string"},
                    },
                },
            },
            {
                "name": "get_current_features",
                "description": "Get flattened current observation features for one station, all stations, or the nearest station to a location.",
                "method": "POST",
                "endpoint": "/api/v1/ai/tools/call",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "station_id": {"type": "integer"},
                        "station_name": {"type": "string"},
                        "lat": {"type": "number"},
                        "lon": {"type": "number"},
                    },
                },
            },
            {
                "name": "get_latest_documents",
                "description": "Get the latest forecast and bulletin documents used for RAG and citations.",
                "method": "POST",
                "endpoint": "/api/v1/ai/tools/call",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "document_type": {
                            "type": "string",
                            "enum": ["forecast_48h", "weekly_forecast_pdf", "agro_bulletin_pdf"],
                        },
                    },
                },
            },
            {
                "name": "get_location_context",
                "description": "Get one location bundle with nearest station, latest structured observation features, and latest forecast/bulletin documents.",
                "method": "POST",
                "endpoint": "/api/v1/ai/tools/call",
                "input_schema": {
                    "type": "object",
                    "required": ["lat", "lon"],
                    "properties": {
                        "lat": {"type": "number"},
                        "lon": {"type": "number"},
                    },
                },
            },
            {
                "name": "get_agro_advisory",
                "description": "Estimate crop phase, explainable agroclimatic risk, and preventive recommendations for maize or bean.",
                "method": "POST",
                "endpoint": "/api/v1/ai/tools/call",
                "input_schema": {
                    "type": "object",
                    "required": ["crop", "sowing_date", "lat", "lon"],
                    "properties": {
                        "crop": {"type": "string", "enum": ["maiz", "frijol"]},
                        "sowing_date": {"type": "string", "format": "date"},
                        "target_date": {"type": "string", "format": "date"},
                        "lat": {"type": "number"},
                        "lon": {"type": "number"},
                        "rain_sum_mm": {"type": "number"},
                        "et0_sum_mm": {"type": "number"},
                        "days_window": {"type": "integer"},
                        "dry_days": {"type": "integer"},
                        "temp_max_c": {"type": "number"},
                        "wind_max_kmh": {"type": "number"},
                        "et0_mm_day": {"type": "number"},
                        "soil": {
                            "type": "string",
                            "enum": ["favorable", "neutral", "unfavorable"],
                        },
                        "seasonal": {
                            "type": "string",
                            "enum": [
                                "arriba_lo_normal",
                                "normal",
                                "bajo_lo_normal",
                                "canicula_o_sequia_fuerte",
                            ],
                        },
                        "canicula_watch": {"type": "boolean"},
                    },
                },
            },
            {
                "name": "getRiskAssessment",
                "description": "Manifest-aligned risk assessment for maize or bean using observed, forecast, geo, and official context.",
                "method": "POST",
                "endpoint": "/api/v1/ai/tools/call",
                "input_schema": {
                    "type": "object",
                    "required": ["crop", "sowing_date", "lat", "lon"],
                    "properties": {
                        "crop": {"type": "string", "enum": ["maiz", "frijol"]},
                        "sowing_date": {"type": "string", "format": "date"},
                        "target_date": {"type": "string", "format": "date"},
                        "lat": {"type": "number"},
                        "lon": {"type": "number"},
                        "municipality": {"type": "string"},
                        "municipality_code": {"type": "string"},
                        "canton": {"type": "string"},
                    },
                },
            },
            {
                "name": "getOfficialContext",
                "description": "Return official 2026 canicula context and seasonal explanation snippets.",
                "method": "POST",
                "endpoint": "/api/v1/ai/tools/call",
                "input_schema": {
                    "type": "object",
                    "required": ["target_date"],
                    "properties": {
                        "lat": {"type": "number"},
                        "lon": {"type": "number"},
                        "target_date": {"type": "string", "format": "date"},
                    },
                },
            },
            {
                "name": "getPhenologyContext",
                "description": "Return estimated phase and uncertainty from crop plus sowing date.",
                "method": "POST",
                "endpoint": "/api/v1/ai/tools/call",
                "input_schema": {
                    "type": "object",
                    "required": ["crop", "sowing_date"],
                    "properties": {
                        "crop": {"type": "string", "enum": ["maiz", "frijol"]},
                        "sowing_date": {"type": "string", "format": "date"},
                        "target_date": {"type": "string", "format": "date"},
                    },
                },
            },
            {
                "name": "explainRecommendation",
                "description": "Turn risk assessment plus official context into a simple explanation for the producer or extension team.",
                "method": "POST",
                "endpoint": "/api/v1/ai/tools/call",
                "input_schema": {
                    "type": "object",
                    "required": ["risk_assessment"],
                    "properties": {
                        "risk_assessment": {"type": "object"},
                        "official_context": {"type": "object"},
                        "plant_state": {"type": "object"},
                        "recommendations": {"type": "array"},
                        "audience": {"type": "string"},
                    },
                },
            },
        ],
    })


@bp.route("/call", methods=["POST"])
def call():
    """Generic function-calling endpoint for LLM clients."""
    payload = request.get_json(silent=True) or {}
    tool_name = payload.get("tool_name")
    arguments = payload.get("arguments") or {}

    if not tool_name:
        return jsonify({"error": "tool_name is required"}), 400

    body, status = _call_tool(tool_name, arguments)
    return jsonify(body), status
