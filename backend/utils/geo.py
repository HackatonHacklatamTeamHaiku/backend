"""
Geospatial helpers — Haversine distance & nearest-station lookup.
"""

from __future__ import annotations

import math
from typing import Sequence


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in **kilometres** between two points."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest(
    lat: float,
    lon: float,
    stations: Sequence[dict],
    lat_key: str = "lat",
    lon_key: str = "lon",
) -> dict | None:
    """Return the station dict closest to ``(lat, lon)``."""
    if not stations:
        return None
    return min(
        stations,
        key=lambda s: haversine(lat, lon, s[lat_key], s[lon_key]),
    )
