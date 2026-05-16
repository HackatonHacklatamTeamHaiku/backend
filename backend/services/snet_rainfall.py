"""
Fetch raw recent rainfall observations from SNET lluvia_data_24h.
"""

from __future__ import annotations

import logging

from config import Config
from utils.http import session

logger = logging.getLogger(__name__)


def fetch_all() -> str:
    """Return the raw JS-like payload for all recent rainfall stations."""
    logger.info("Fetching rainfall observations from SNET")
    resp = session.get(Config.SNET_RAINFALL_URL, timeout=Config.HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.text
