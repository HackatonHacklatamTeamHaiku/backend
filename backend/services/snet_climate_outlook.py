"""
Fetch monthly climate outlook point data from SNET.
"""

from __future__ import annotations

import logging

from config import Config
from utils.http import get_json

logger = logging.getLogger(__name__)


def fetch_point(layer_id: int, lat: float, lon: float) -> dict:
    logger.info("Fetching climate outlook for layer=%s lat=%s lon=%s", layer_id, lat, lon)
    url = Config.SNET_CLIMATE_OUTLOOK_URL_TEMPLATE.format(layer_id=layer_id)
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "gridcode,Escenario",
        "returnGeometry": "false",
        "f": "pjson",
    }
    return get_json(url, params=params)
