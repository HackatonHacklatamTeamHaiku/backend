"""
Normalize and query basin polygons from the JS-style SNET payload.
"""

from __future__ import annotations

import json
import re


_UNQUOTED_KEY_RE = re.compile(r'([{\[,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)')


def _js_array_to_json(raw_text: str) -> list[dict]:
    normalized = raw_text.strip()
    normalized = _UNQUOTED_KEY_RE.sub(r'\1"\2"\3', normalized)
    normalized = normalized.replace("'", '"')
    return json.loads(normalized)


def _parse_polygon(raw_polygon: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for pair in raw_polygon.split(","):
        pair = pair.strip()
        if not pair:
            continue
        lon_str, lat_str = pair.split()
        points.append((float(lon_str), float(lat_str)))
    return points


def normalize_basins(raw_text: str) -> list[dict]:
    basins = _js_array_to_json(raw_text)
    normalized: list[dict] = []
    for item in basins:
        raw_polygon = item.get("poligono")
        if not raw_polygon:
            continue
        normalized.append(
            {
                "source": "snet_datos_cuencas",
                "basin_id": str(item.get("nombre") or ""),
                "level": item.get("nivel"),
                "polygon": _parse_polygon(raw_polygon),
            }
        )
    return normalized


def point_in_polygon(lon: float, lat: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test."""
    inside = False
    total = len(polygon)
    if total < 3:
        return False

    j = total - 1
    for i in range(total):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def basin_for_point(lat: float, lon: float, basins: list[dict]) -> dict | None:
    for basin in basins:
        polygon = basin.get("polygon") or []
        if point_in_polygon(lon, lat, polygon):
            return basin
    return None
