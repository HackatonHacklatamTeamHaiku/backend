"""
Normalize raw SNET temperature + wind JSON into ``Observation`` objects.

Merge strategy:
  1. Index temperature features by ``estacionid``
  2. Index wind features by ``estacionid``
  3. Build one combined ``Observation`` per station
"""

from __future__ import annotations

import logging
from typing import Optional

from models.schemas import Observation, Temperature, Wind
from utils.time import epoch_ms_to_iso, epoch_ms_to_local

logger = logging.getLogger(__name__)


def _extract_features(raw_json: dict) -> list[dict]:
    """Pull out the ``features[].attributes`` list from ArcGIS JSON."""
    return [
        f["attributes"]
        for f in raw_json.get("features", [])
        if "attributes" in f
    ]


def extract_station_ids(*raw_payloads: dict) -> set[int]:
    """Collect all station ids present in one or more ArcGIS payloads."""
    station_ids: set[int] = set()
    for raw in raw_payloads:
        for attrs in _extract_features(raw):
            sid = attrs.get("estacionid")
            if sid is not None:
                station_ids.add(sid)
    return station_ids


def normalize_temperature(raw: dict) -> dict[int, dict]:
    """Return a dict keyed by station_id with temp fields."""
    result: dict[int, dict] = {}
    for attrs in _extract_features(raw):
        sid = attrs.get("estacionid")
        if sid is None:
            continue
        result[sid] = {
            "station_id": sid,
            "lat": attrs.get("latitud"),
            "lon": attrs.get("longitud"),
            "observed_at": epoch_ms_to_iso(attrs.get("horafecha")),
            "observed_at_local": epoch_ms_to_local(attrs.get("horafecha")),
            "temperature": Temperature(
                current_c=attrs.get("actual"),
                max_c=attrs.get("maxima"),
                min_c=attrs.get("minima"),
            ),
        }
    return result


def normalize_wind(raw: dict) -> dict[int, dict]:
    """Return a dict keyed by station_id with wind fields."""
    result: dict[int, dict] = {}
    for attrs in _extract_features(raw):
        sid = attrs.get("estacionid")
        if sid is None:
            continue
        result[sid] = {
            "station_id": sid,
            "lat": attrs.get("latitud"),
            "lon": attrs.get("longitud"),
            "wind": Wind(
                direction_deg=attrs.get("dir_promedio"),
                speed=attrs.get("vel_promedio"),
            ),
        }
    return result


def merge_observations(
    temp_raw: dict,
    wind_raw: dict,
    station_id: Optional[int] = None,
    station_metadata: Optional[dict[int, dict]] = None,
) -> list[Observation]:
    """Merge temperature and wind data into a list of ``Observation``s.

    If ``station_id`` is given, only that station is returned.
    """
    temps = normalize_temperature(temp_raw)
    winds = normalize_wind(wind_raw)
    station_metadata = station_metadata or {}

    all_ids = set(temps.keys()) | set(winds.keys())
    if station_id is not None:
        all_ids = {station_id} & all_ids

    observations: list[Observation] = []
    for sid in sorted(all_ids):
        t = temps.get(sid, {})
        w = winds.get(sid, {})
        meta = station_metadata.get(sid, {})
        station_name = meta.get("station_name") or f"SNET Station {sid}"

        obs = Observation(
            station_id=sid,
            station_code=meta.get("station_code", f"snet-{sid}"),
            station_name=station_name,
            station_label=meta.get("station_label", f"{station_name} weather station"),
            station_name_source=meta.get("station_name_source", "generated"),
            lat=w.get("lat") or t.get("lat") or meta.get("metadata_lat") or 0.0,
            lon=w.get("lon") or t.get("lon") or meta.get("metadata_lon") or 0.0,
            observed_at=t.get("observed_at"),
            observed_at_local=t.get("observed_at_local"),
            temperature=t.get("temperature", Temperature()),
            wind=w.get("wind", Wind()),
        )
        observations.append(obs)

    logger.info("Merged %d observations", len(observations))
    return observations
