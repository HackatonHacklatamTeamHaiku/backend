"""
Fetch basin polygons from the JS-style datos_cuencas endpoint.
"""

from __future__ import annotations

import logging

from config import Config
from utils.http import session

logger = logging.getLogger(__name__)


def fetch_all() -> str:
    logger.info("Fetching basin polygons from SNET")
    resp = session.get(Config.SNET_BASINS_URL, timeout=Config.HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.text
