from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from services.manifest_context import get_geo_context
from utils.time import EL_SALVADOR_TZ

bp = Blueprint("geo", __name__, url_prefix="/api/geo")


@bp.route("/context")
def geo_context():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    target_date = request.args.get("target_date", type=str)
    if lat is None or lon is None:
        return jsonify({"error": "lat and lon query parameters are required"}), 400

    target = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else datetime.now(EL_SALVADOR_TZ).date()
    data, meta = get_geo_context(
        lat,
        lon,
        target,
        municipality=request.args.get("municipality", type=str),
        municipality_code=request.args.get("municipality_code", type=str),
        canton=request.args.get("canton", type=str),
    )
    return jsonify({"data": data, "meta": meta})
