from __future__ import annotations

from uuid import uuid4

from flask import Blueprint, jsonify, request

from routes.request_validation import empty_param_error, invalid_request, repeated_param_error
from services.manifest_context import build_runtime_llm_context, explain_recommendation
from services.openrouter_llm import generate_chat_reply

bp = Blueprint("llm", __name__, url_prefix="/api/llm")


@bp.route("/context")
def llm_context():
    repeated_error = repeated_param_error(request.args, ["crop", "sowing_date", "lat", "lon", "target_date"])
    empty_error = empty_param_error(request.args, ["crop", "sowing_date", "lat", "lon", "target_date"])
    if repeated_error or empty_error:
        return invalid_request(repeated_error or empty_error)
    data, meta, status = build_runtime_llm_context(request.args.to_dict())
    return jsonify({"data": data, "meta": meta}), status


@bp.route("/explain", methods=["POST"])
def llm_explain():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return invalid_request("JSON body must be an object")
    risk_assessment = payload.get("risk_assessment")
    if not isinstance(risk_assessment, dict):
        return invalid_request("risk_assessment must be an object")
    for field in ("risk_factors", "secondary_alerts"):
        if field in risk_assessment and not isinstance(risk_assessment[field], list):
            return invalid_request(f"risk_assessment.{field} must be a list")
        if any(not isinstance(item, dict) for item in risk_assessment.get(field) or []):
            return invalid_request(f"risk_assessment.{field} items must be objects")
    if "recommendations" in payload and not isinstance(payload["recommendations"], list):
        return invalid_request("recommendations must be a list")
    for field in ("official_context", "plant_state"):
        if field in payload and not isinstance(payload[field], dict):
            return invalid_request(f"{field} must be an object")
    return jsonify({"data": explain_recommendation(payload)})


@bp.route("/chat", methods=["POST"])
def llm_chat():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return invalid_request("JSON body must be an object")
    conversation_id = _conversation_id_from_payload(payload)
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    data, meta, status = generate_chat_reply(
        payload,
        langsmith_extra={
            "tags": ["api", "llm-chat", "thread"],
            "metadata": {
                "conversation_id": conversation_id,
                "session_id": conversation_id,
                "thread_id": conversation_id,
                "request_id": request_id,
                "route": "POST /api/llm/chat",
            },
        },
    )
    if isinstance(data, dict):
        data.setdefault("conversation_id", conversation_id)
    return jsonify({"data": data, "meta": meta}), status


def _conversation_id_from_payload(payload: dict) -> str:
    raw = payload.get("conversation_id") or payload.get("thread_id") or payload.get("session_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:120]
    return str(uuid4())
