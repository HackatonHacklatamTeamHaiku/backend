from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from services.manifest_context import get_weather_forecast, get_weather_observed
from utils.time import EL_SALVADOR_TZ

bp = Blueprint("weather", __name__, url_prefix="/api/weather")


@bp.route("/observed")
def weather_observed():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"error": "lat and lon query parameters are required"}), 400
    data, meta = get_weather_observed(lat, lon)
    return jsonify({"data": data, "meta": meta})


@bp.route("/forecast")
def weather_forecast():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    target_date = request.args.get("target_date", type=str)
    if lat is None or lon is None:
        return jsonify({"error": "lat and lon query parameters are required"}), 400
    target = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else datetime.now(EL_SALVADOR_TZ).date()
    data, meta = get_weather_forecast(lat, lon, target)
    return jsonify({"data": data, "meta": meta})
