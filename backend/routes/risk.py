from __future__ import annotations

from flask import Blueprint, jsonify, request

from routes.request_validation import empty_param_error, invalid_request, repeated_param_error
from services.manifest_context import get_risk_assessment

bp = Blueprint("risk", __name__, url_prefix="/api/risk")


@bp.route("/assessment")
def risk_assessment():
    repeated_error = repeated_param_error(request.args, ["crop", "sowing_date", "lat", "lon", "target_date"])
    empty_error = empty_param_error(request.args, ["crop", "sowing_date", "lat", "lon", "target_date"])
    if repeated_error or empty_error:
        return invalid_request(repeated_error or empty_error)
    data, meta, status = get_risk_assessment(request.args.to_dict())
    return jsonify({"data": data, "meta": meta}), status
