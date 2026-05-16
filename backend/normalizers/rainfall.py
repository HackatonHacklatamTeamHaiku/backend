"""
Normalize SNET lluvia_data_24h payloads into plain dict records.
"""

from __future__ import annotations

import json
import re


_UNQUOTED_KEY_RE = re.compile(r'([{\[,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)')


def _js_array_to_json(raw_text: str) -> list[dict]:
    """Convert the endpoint's JS-style array literal into Python data."""
    normalized = raw_text.strip()
    normalized = _UNQUOTED_KEY_RE.sub(r'\1"\2"\3', normalized)
    normalized = normalized.replace("'", '"')
    return json.loads(normalized)


def normalize_rainfall(raw_text: str) -> list[dict]:
    """Return normalized recent rainfall records from the raw JS payload."""
    records = _js_array_to_json(raw_text)
    normalized: list[dict] = []

    for item in records:
        station_id = item.get("estacion")
        lat = item.get("latitud")
        lon = item.get("longitud")
        rain_mm = item.get("valor_acumulado")

        if station_id is None or lat is None or lon is None:
            continue

        normalized.append(
            {
                "source": "snet_lluvia_data_24h",
                "station_id": int(station_id),
                "station_name": item.get("nombre_estacion") or f"SNET Rain Station {station_id}",
                "lat": float(lat),
                "lon": float(lon),
                "obs_time_start_local": item.get("hora_inicial"),
                "obs_time_latest_local": item.get("hora_reciente"),
                "rain_mm_period": float(rain_mm or 0.0),
                "is_raining": bool(item.get("llueve")),
                "raw_initial_reading": item.get("valor_inicial"),
                "raw_max_reading": item.get("valor_maximo"),
                "temporal_role": "short_term",
                "current_for_alerting": True,
            }
        )

    return normalized
