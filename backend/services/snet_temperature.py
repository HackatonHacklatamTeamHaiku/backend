"""
Fetch raw temperature observations from SNET.
"""

import logging

from config import Config
from utils.http import get_json

logger = logging.getLogger(__name__)

# Default query parameters for the ArcGIS endpoint
_DEFAULT_PARAMS = {
    "where": "1=1",
    "outFields": "estacionid,latitud,longitud,horafecha,actual,maxima,minima",
    "returnGeometry": "false",
    "f": "pjson",
}


def fetch_all() -> dict:
    """Return the raw ArcGIS JSON for all temperature stations."""
    logger.info("Fetching temperature observations from SNET")
    return get_json(Config.SNET_TEMPERATURE_URL, params=_DEFAULT_PARAMS)


def fetch_by_station(station_id: int) -> dict:
    """Return the raw ArcGIS JSON for a single station."""
    params = {
        **_DEFAULT_PARAMS,
        "where": f"estacionid = {station_id}",
    }
    logger.info("Fetching temperature for station %s", station_id)
    return get_json(Config.SNET_TEMPERATURE_URL, params=params)
