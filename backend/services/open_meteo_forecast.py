"""
Fetch Open-Meteo forecast data for the SATO-Agro manifest contract.
"""

from __future__ import annotations

import logging

from utils.http import get_json

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def fetch(lat: float, lon: float, forecast_days: int = 16) -> dict:
    logger.info("Fetching Open-Meteo forecast for lat=%s lon=%s", lat, lon)
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "et0_fao_evapotranspiration_sum",
            ]
        ),
        "hourly": ",".join(
            [
                "soil_moisture_0_to_1cm",
                "soil_moisture_1_to_3cm",
                "soil_moisture_3_to_9cm",
                "precipitation",
                "temperature_2m",
                "wind_speed_10m",
            ]
        ),
        "forecast_days": forecast_days,
        "timezone": "America/El_Salvador",
    }
    return get_json(OPEN_METEO_FORECAST_URL, params=params)
