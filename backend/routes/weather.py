from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from routes.request_validation import empty_param_error, invalid_request, repeated_param_error
from services.manifest_context import (
    _parse_coordinate,
    _parse_request_date,
    _validate_supported_location,
    get_weather_forecast,
    get_weather_observed,
)
from utils.time import EL_SALVADOR_TZ

bp = Blueprint("weather", __name__, url_prefix="/api/weather")


@bp.route("/observed")
def weather_observed():
    repeated_error = repeated_param_error(request.args, ["lat", "lon"])
    empty_error = empty_param_error(request.args, ["lat", "lon"])
    if repeated_error or empty_error:
        return invalid_request(repeated_error or empty_error)
    if request.args.get("lat") is None or request.args.get("lon") is None:
        return invalid_request("lat and lon query parameters are required")
    try:
        lat = _parse_coordinate(request.args.get("lat"), "lat")
        lon = _parse_coordinate(request.args.get("lon"), "lon")
        _validate_supported_location(lat, lon)
    except ValueError as exc:
        return invalid_request(str(exc))
    data, meta = get_weather_observed(lat, lon)
    return jsonify({"data": data, "meta": meta})


@bp.route("/forecast")
def weather_forecast():
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
        if target < datetime.now(EL_SALVADOR_TZ).date():
            return invalid_request("target_date cannot be earlier than today for weather forecast")
    except ValueError as exc:
        return invalid_request(str(exc))
    data, meta = get_weather_forecast(lat, lon, target)
    return jsonify({"data": data, "meta": meta})
