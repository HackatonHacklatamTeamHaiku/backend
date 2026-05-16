from __future__ import annotations

from datetime import datetime

from services.manifest_context import (
    explain_recommendation,
    get_official_context,
    get_phenology_context,
    get_risk_assessment,
)
from utils.time import EL_SALVADOR_TZ, now_utc_iso


def semantic_tool_manifest() -> list[dict]:
    return [
        {
            "name": "getRiskAssessment",
            "description": "Calcula estado de planta, clima relevante, factores de riesgo, nivel, confianza y recomendaciones para una fecha especifica.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "crop": {"type": "string", "enum": ["maiz", "frijol"]},
                    "sowing_date": {"type": "string", "format": "date"},
                    "target_date": {"type": "string", "format": "date"},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                },
                "required": ["crop", "sowing_date", "lat", "lon"],
            },
        },
        {
            "name": "getOfficialContext",
            "description": "Obtiene contexto oficial vigente o relevante sobre canicula, perspectiva climatica, sequia o boletines agroclimaticos.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "target_date": {"type": "string", "format": "date"},
                },
            },
        },
        {
            "name": "getPhenologyContext",
            "description": "Calcula o explica la fase estimada del cultivo para una fecha especifica usando cultivo y fecha de siembra.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "crop": {"type": "string", "enum": ["maiz", "frijol"]},
                    "sowing_date": {"type": "string", "format": "date"},
                    "target_date": {"type": "string", "format": "date"},
                },
                "required": ["crop", "sowing_date"],
            },
        },
        {
            "name": "explainRecommendation",
            "description": "Convierte una evaluacion de riesgo y contexto oficial en una explicacion breve, clara y accionable para productor o tecnico.",
            "input_schema": {
                "type": "object",
                "required": ["risk_assessment"],
                "properties": {
                    "risk_assessment": {"type": "object"},
                    "official_context": {"type": "object"},
                    "audience": {"type": "string", "enum": ["productor", "tecnico"]},
                },
            },
        },
    ]


def openrouter_tool_definitions() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in semantic_tool_manifest()
    ]


def execute_semantic_tool(tool_name: str, arguments: dict) -> tuple[dict, dict, int]:
    if tool_name == "getRiskAssessment":
        return get_risk_assessment(arguments)

    if tool_name == "getOfficialContext":
        target_date = arguments.get("target_date")
        resolved_target_date = (
            datetime.strptime(target_date, "%Y-%m-%d").date()
            if target_date
            else datetime.now(EL_SALVADOR_TZ).date()
        )
        return get_official_context(resolved_target_date), _tool_meta(), 200

    if tool_name == "getPhenologyContext":
        crop = arguments.get("crop")
        sowing_date = arguments.get("sowing_date")
        if not crop or not sowing_date:
            return {"error": "crop and sowing_date are required"}, _tool_meta("invalid_request"), 400
        return get_phenology_context(crop, sowing_date, arguments.get("target_date")), _tool_meta(), 200

    if tool_name == "explainRecommendation":
        return explain_recommendation(arguments), _tool_meta(), 200

    return {"error": f"Unknown tool_name: {tool_name}"}, _tool_meta("not_found"), 404


def _tool_meta(upstream_status: str = "ok") -> dict:
    return {
        "cached": True,
        "stale": False,
        "upstream_status": upstream_status,
        "fetched_at": now_utc_iso(),
    }
