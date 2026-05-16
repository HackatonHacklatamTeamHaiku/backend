"""
Point lookup against municipal boundaries from ExposicionASequia layer 0.
"""

from __future__ import annotations

import logging

from config import Config
from utils.http import get_json

logger = logging.getLogger(__name__)


def fetch_point(lat: float, lon: float) -> dict:
    logger.info("Fetching municipality boundary for lat=%s lon=%s", lat, lon)
    url = Config.SNET_MUNICIPAL_BOUNDARIES_URL
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "COD,NAM,NA2,NA3",
        "returnGeometry": "false",
        "f": "pjson",
    }
    return get_json(url, params=params)
