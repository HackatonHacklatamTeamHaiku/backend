"""
Dashboard summary endpoint.

GET /api/v1/dashboard/summary?lat=&lon= — combined payload for the app
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from config import Config
from services import snet_station_metadata, snet_temperature, snet_wind, snet_forecast_48h
from services import snet_weekly_pdf, snet_agro_pdf
from normalizers.observations import extract_station_ids, merge_observations
from normalizers.forecasts import normalize_48h
from normalizers.agro import normalize_pdf
from models.schemas import to_dict
from utils.cache import DataCache
from utils.geo import find_nearest
from utils.time import now_utc_iso

logger = logging.getLogger(__name__)

bp = Blueprint("dashboard", __name__, url_prefix="/api/v1/dashboard")

# Individual caches for each data source
_cache_obs = DataCache(ttl=Config.CACHE_TTL_OBSERVATIONS)
_cache_48h = DataCache(ttl=Config.CACHE_TTL_FORECAST_48H)
_cache_weekly = DataCache(ttl=Config.CACHE_TTL_WEEKLY_PDF)
_cache_agro = DataCache(ttl=Config.CACHE_TTL_AGRO_PDF)


def _get_observations() -> tuple[list[dict], bool]:
    """Fetch observations with cache fallback."""
    cached, stale = _cache_obs.get()
    if cached is not None and not stale:
        return cached, False
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
        _cache_obs.set(data)
        return data, False
    except Exception:
        logger.exception("Dashboard: failed to fetch observations")
        return cached or [], cached is not None


def _get_forecast_48h() -> tuple[dict | None, bool]:
    """Fetch 48h forecast with cache fallback."""
    cached, stale = _cache_48h.get()
    if cached is not None and not stale:
        return cached, False
    try:
        html = snet_forecast_48h.fetch()
        forecast = normalize_48h(html)
        data = to_dict(forecast)
        _cache_48h.set(data)
        return data, False
    except Exception:
        logger.exception("Dashboard: failed to fetch 48h forecast")
        return cached, cached is not None


def _get_weekly_pdf() -> tuple[dict | None, bool]:
    """Fetch weekly PDF meta with cache fallback."""
    cached, stale = _cache_weekly.get()
    if cached is not None and not stale:
        return cached, False
    try:
        raw = snet_weekly_pdf.fetch()
        pdf_meta = normalize_pdf(raw, "weekly_forecast")
        data = to_dict(pdf_meta)
        _cache_weekly.set(data)
        return data, False
    except Exception:
        logger.exception("Dashboard: failed to fetch weekly PDF")
        return cached, cached is not None


def _get_agro_pdf() -> tuple[dict | None, bool]:
    """Fetch agro PDF meta with cache fallback."""
    cached, stale = _cache_agro.get()
    if cached is not None and not stale:
        return cached, False
    try:
        raw = snet_agro_pdf.fetch()
        pdf_meta = normalize_pdf(raw, "agro_bulletin")
        data = to_dict(pdf_meta)
        _cache_agro.set(data)
        return data, False
    except Exception:
        logger.exception("Dashboard: failed to fetch agro PDF")
        return cached, cached is not None


@bp.route("/summary")
def summary():
    """Return one combined payload with all data sources."""
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)

    if lat is None or lon is None:
        return jsonify({"error": "lat and lon query parameters are required"}), 400

    # Fetch all sources (each with independent cache + fallback)
    obs_data, obs_stale = _get_observations()
    forecast_data, forecast_stale = _get_forecast_48h()
    weekly_data, weekly_stale = _get_weekly_pdf()
    agro_data, agro_stale = _get_agro_pdf()

    # Find nearest station
    nearest = find_nearest(lat, lon, obs_data) if obs_data else None

    any_stale = obs_stale or forecast_stale or weekly_stale or agro_stale

    return jsonify({
        "location": {"lat": lat, "lon": lon},
        "nearest_observation": nearest,
        "forecast_48h": forecast_data,
        "weekly_forecast": weekly_data,
        "agro_bulletin": agro_data,
        "meta": {
            "cached": True,
            "stale": any_stale,
            "upstream_status": "degraded" if any_stale else "ok",
            "fetched_at": now_utc_iso(),
        },
    })
