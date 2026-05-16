"""
Fetch the raw 48-hour forecast HTML page from SNET.
"""

import logging

from config import Config
from utils.http import get_html

logger = logging.getLogger(__name__)


def fetch() -> str:
    """Return the full HTML text of the 48-hour forecast page."""
    logger.info("Fetching 48-hour forecast page from SNET")
    return get_html(Config.SNET_FORECAST_48H_URL)
