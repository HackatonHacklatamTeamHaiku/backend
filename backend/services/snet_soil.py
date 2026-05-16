"""
Fetch soil organic matter summaries used as a structural soil modifier.
"""

from __future__ import annotations

import logging

from config import Config
from utils.http import get_json

logger = logging.getLogger(__name__)


def fetch_all() -> dict:
    logger.info("Fetching soil summaries from SNET")
    params = {
        "where": "1=1",
        "outFields": "First_COD_MUN4,First_mo_txt_descrip,Sum_porc_",
        "returnGeometry": "false",
        "f": "pjson",
    }
    return get_json(Config.SNET_SOIL_URL, params=params)
