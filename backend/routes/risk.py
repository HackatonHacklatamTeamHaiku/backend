from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.manifest_context import get_risk_assessment

bp = Blueprint("risk", __name__, url_prefix="/api/risk")


@bp.route("/assessment")
def risk_assessment():
    data, meta, status = get_risk_assessment(request.args.to_dict())
    return jsonify({"data": data, "meta": meta}), status
