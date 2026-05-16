"""
Observation endpoints.

GET /api/v1/observations/current           — all stations (or ?station_id=N)
GET /api/v1/observations/nearest?lat=&lon= — nearest station
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from config import Config
from services import snet_station_metadata, snet_temperature, snet_wind
from normalizers.observations import extract_station_ids, merge_observations
from models.schemas import to_dict
from utils.cache import DataCache
from utils.geo import find_nearest
from utils.time import now_utc_iso

logger = logging.getLogger(__name__)

bp = Blueprint("observations", __name__, url_prefix="/api/v1/observations")

_cache = DataCache(ttl=Config.CACHE_TTL_OBSERVATIONS)


def _fetch_and_cache() -> tuple[list[dict], bool, str]:
    """Fetch, merge, cache observations. Return (data, is_stale, fetched_at)."""
    cached, stale = _cache.get()
    if cached is not None and not stale:
        return cached, False, _cache.fetched_at() or now_utc_iso()

    try:
        temp_raw = snet_temperature.fetch_all()
        wind_raw = snet_wind.fetch_all()
        station_metadata = snet_station_metadata.get_many(
            extract_station_ids(temp_raw, wind_raw)
        )
        observations = merge_observations(
            temp_raw,
            wind_raw,
            station_metadata=station_metadata,
        )
        data = [to_dict(obs) for obs in observations]
        _cache.set(data)
        return data, False, _cache.fetched_at() or now_utc_iso()
    except Exception:
        logger.exception("Failed to fetch observations from SNET")
        if cached is not None:
            return cached, True, _cache.fetched_at() or now_utc_iso()
        return [], False, now_utc_iso()


@bp.route("/current")
def current_observations():
    """Return current observations, optionally filtered by station_id or name."""
    station_id = request.args.get("station_id", type=int)
    station_name = request.args.get("station_name", type=str)
    data, stale, fetched_at = _fetch_and_cache()

    if station_id is not None:
        data = [o for o in data if o.get("station_id") == station_id]
    if station_name:
        search = station_name.strip().lower()
        data = [
            o for o in data
            if search in (o.get("station_name") or "").lower()
            or search in (o.get("station_code") or "").lower()
        ]

    return jsonify({
        "data": data,
        "meta": {
            "cached": stale or (_cache.get()[0] is not None),
            "stale": stale,
            "upstream_status": "failed" if stale else "ok",
            "fetched_at": fetched_at,
        },
    })


@bp.route("/nearest")
def nearest_observation():
    """Return the single nearest observation to the given lat/lon."""
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)

    if lat is None or lon is None:
        return jsonify({"error": "lat and lon query parameters are required"}), 400

    data, stale, fetched_at = _fetch_and_cache()

    nearest = find_nearest(lat, lon, data)
    return jsonify({
        "data": nearest,
        "meta": {
            "cached": stale or (_cache.get()[0] is not None),
            "stale": stale,
            "upstream_status": "failed" if stale else "ok",
            "fetched_at": fetched_at,
        },
    })
