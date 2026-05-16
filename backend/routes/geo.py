from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from routes.request_validation import empty_param_error, invalid_request, repeated_param_error
from services.manifest_context import (
    _parse_coordinate,
    _parse_request_date,
    _validate_supported_location,
    get_geo_context,
)
from utils.time import EL_SALVADOR_TZ

bp = Blueprint("geo", __name__, url_prefix="/api/geo")


@bp.route("/context")
def geo_context():
    repeated_error = repeated_param_error(request.args, ["lat", "lon", "target_date"])
    empty_error = empty_param_error(request.args, ["lat", "lon", "target_date"])
    if repeated_error or empty_error:
        return invalid_request(repeated_error or empty_error)
    if request.args.get("lat") is None or request.args.get("lon") is None:
        return invalid_request("lat and lon query parameters are required")

    try:
        lat = _parse_coordinate(request.args.get("lat"), "lat")
        lon = _parse_coordinate(request.args.get("lon"), "lon")
        _validate_supported_location(lat, lon)
        target_date = request.args.get("target_date", type=str)
        target = _parse_request_date(target_date, "target_date") if target_date else datetime.now(EL_SALVADOR_TZ).date()
    except ValueError as exc:
        return invalid_request(str(exc))
    data, meta = get_geo_context(
        lat,
        lon,
        target,
        municipality=request.args.get("municipality", type=str),
        municipality_code=request.args.get("municipality_code", type=str),
        canton=request.args.get("canton", type=str),
    )
    return jsonify({"data": data, "meta": meta})
