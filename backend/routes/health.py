"""
Health check endpoint.

GET /health — returns backend and upstream freshness status
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from utils.time import now_utc_iso

logger = logging.getLogger(__name__)

bp = Blueprint("health", __name__)


@bp.route("/health")
def health():
    """Simple health check — always returns 200 if Flask is running."""
    return jsonify({
        "status": "ok",
        "service": "sato-agro-backend",
        "timestamp": now_utc_iso(),
    })
