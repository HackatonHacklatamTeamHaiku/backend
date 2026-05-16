from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.manifest_context import build_runtime_llm_context, explain_recommendation, get_official_context

bp = Blueprint("llm", __name__, url_prefix="/api/llm")


@bp.route("/context")
def llm_context():
    target_date = request.args.get("target_date")
    if not request.args.get("crop") or not request.args.get("sowing_date") or request.args.get("lat") is None or request.args.get("lon") is None:
        # If the caller only wants official snippets, return a minimal context.
        if target_date:
            from datetime import datetime

            context = get_official_context(datetime.strptime(target_date, "%Y-%m-%d").date())
            return jsonify({"data": {"official_context": context}, "meta": {"cached": True, "stale": False, "upstream_status": "ok"}})
    data, meta, status = build_runtime_llm_context(request.args.to_dict())
    return jsonify({"data": data, "meta": meta}), status


@bp.route("/explain", methods=["POST"])
def llm_explain():
    payload = request.get_json(silent=True) or {}
    if "risk_assessment" not in payload:
        return jsonify({"error": "risk_assessment is required"}), 400
    return jsonify({"data": explain_recommendation(payload)})
