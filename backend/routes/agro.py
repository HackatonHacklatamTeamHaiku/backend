"""
Agro bulletin endpoint.

GET /api/v1/agro/latest — latest agro bulletin PDF metadata
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from config import Config
from services import snet_agro_pdf
from normalizers.agro import normalize_pdf
from models.schemas import to_dict
from utils.cache import DataCache
from utils.time import now_utc_iso

logger = logging.getLogger(__name__)

bp = Blueprint("agro", __name__, url_prefix="/api/v1/agro")

_cache = DataCache(ttl=Config.CACHE_TTL_AGRO_PDF)


@bp.route("/latest")
def latest_agro():
    """Return the latest agro bulletin PDF metadata."""
    cached, stale = _cache.get()
    if cached is not None and not stale:
        return jsonify({
            "data": cached,
            "meta": {"cached": True, "stale": False, "upstream_status": "ok",
                     "fetched_at": _cache.fetched_at()},
        })

    try:
        raw = snet_agro_pdf.fetch()
        pdf_meta = normalize_pdf(raw, "agro_bulletin")
        data = to_dict(pdf_meta)
        _cache.set(data)
        return jsonify({
            "data": data,
            "meta": {"cached": False, "stale": False, "upstream_status": "ok",
                     "fetched_at": _cache.fetched_at()},
        })
    except Exception:
        logger.exception("Failed to fetch agro bulletin")
        if cached is not None:
            return jsonify({
                "data": cached,
                "meta": {"cached": True, "stale": True, "upstream_status": "failed",
                         "fetched_at": _cache.fetched_at()},
            })
        return jsonify({
            "data": None,
            "meta": {"cached": False, "stale": False, "upstream_status": "failed",
                     "fetched_at": now_utc_iso()},
        }), 502
