"""
Fetch raw wind observations from SNET.
"""

import logging

from config import Config
from utils.http import get_json

logger = logging.getLogger(__name__)

_DEFAULT_PARAMS = {
    "where": "1=1",
    "outFields": "estacionid,latitud,longitud,dir_promedio,vel_promedio",
    "returnGeometry": "false",
    "f": "pjson",
}


def fetch_all() -> dict:
    """Return the raw ArcGIS JSON for all wind stations."""
    logger.info("Fetching wind observations from SNET")
    return get_json(Config.SNET_WIND_URL, params=_DEFAULT_PARAMS)


def fetch_by_station(station_id: int) -> dict:
    """Return the raw ArcGIS JSON for a single wind station."""
    params = {
        **_DEFAULT_PARAMS,
        "where": f"estacionid = {station_id}",
    }
    logger.info("Fetching wind for station %s", station_id)
    return get_json(Config.SNET_WIND_URL, params=params)
