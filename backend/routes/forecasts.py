"""
Forecast endpoints.

GET /api/v1/forecast/48h    — 48-hour forecast
GET /api/v1/forecast/weekly — latest weekly forecast PDF metadata
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from config import Config
from services import snet_forecast_48h, snet_weekly_pdf
from normalizers.forecasts import normalize_48h
from normalizers.agro import normalize_pdf
from models.schemas import to_dict
from utils.cache import DataCache
from utils.time import now_utc_iso

logger = logging.getLogger(__name__)

bp = Blueprint("forecasts", __name__, url_prefix="/api/v1/forecast")

_cache_48h = DataCache(ttl=Config.CACHE_TTL_FORECAST_48H)
_cache_weekly = DataCache(ttl=Config.CACHE_TTL_WEEKLY_PDF)


@bp.route("/48h")
def forecast_48h():
    """Return the normalized 48-hour forecast."""
    cached, stale = _cache_48h.get()
    if cached is not None and not stale:
        return jsonify({
            "data": cached,
            "meta": {"cached": True, "stale": False, "upstream_status": "ok",
                     "fetched_at": _cache_48h.fetched_at()},
        })

    try:
        html = snet_forecast_48h.fetch()
        forecast = normalize_48h(html)
        data = to_dict(forecast)
        _cache_48h.set(data)
        return jsonify({
            "data": data,
            "meta": {"cached": False, "stale": False, "upstream_status": "ok",
                     "fetched_at": _cache_48h.fetched_at()},
        })
    except Exception:
        logger.exception("Failed to fetch 48h forecast")
        if cached is not None:
            return jsonify({
                "data": cached,
                "meta": {"cached": True, "stale": True, "upstream_status": "failed",
                         "fetched_at": _cache_48h.fetched_at()},
            })
        return jsonify({
            "data": None,
            "meta": {"cached": False, "stale": False, "upstream_status": "failed",
                     "fetched_at": now_utc_iso()},
        }), 502


@bp.route("/weekly")
def weekly_forecast():
    """Return the latest weekly forecast PDF metadata."""
    cached, stale = _cache_weekly.get()
    if cached is not None and not stale:
        return jsonify({
            "data": cached,
            "meta": {"cached": True, "stale": False, "upstream_status": "ok",
                     "fetched_at": _cache_weekly.fetched_at()},
        })

    try:
        raw = snet_weekly_pdf.fetch()
        pdf_meta = normalize_pdf(raw, "weekly_forecast")
        data = to_dict(pdf_meta)
        _cache_weekly.set(data)
        return jsonify({
            "data": data,
            "meta": {"cached": False, "stale": False, "upstream_status": "ok",
                     "fetched_at": _cache_weekly.fetched_at()},
        })
    except Exception:
        logger.exception("Failed to fetch weekly forecast PDF")
        if cached is not None:
            return jsonify({
                "data": cached,
                "meta": {"cached": True, "stale": True, "upstream_status": "failed",
                         "fetched_at": _cache_weekly.fetched_at()},
            })
        return jsonify({
            "data": None,
            "meta": {"cached": False, "stale": False, "upstream_status": "failed",
                     "fetched_at": now_utc_iso()},
        }), 502
