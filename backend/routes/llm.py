from __future__ import annotations

from flask import Blueprint, jsonify, request

from routes.request_validation import empty_param_error, invalid_request, repeated_param_error
from services.manifest_context import build_runtime_llm_context, explain_recommendation

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
    if "risk_assessment" not in payload:
        return jsonify({"error": "risk_assessment is required"}), 400
    return jsonify({"data": explain_recommendation(payload)})
