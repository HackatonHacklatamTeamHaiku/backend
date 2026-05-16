"""
Normalize municipality point lookups from ExposicionASequia layer 0.
"""

from __future__ import annotations


def normalize_municipality_feature(raw_json: dict, *, lat: float, lon: float) -> dict | None:
    features = raw_json.get("features") or []
    if not features:
        return None

    attrs = features[0].get("attributes") or {}
    municipality_name = attrs.get("NAM") or attrs.get("NA2")
    municipality_code = attrs.get("NA3")
    return {
        "source": "snet_municipal_boundaries",
        "lat": lat,
        "lon": lon,
        "municipality": municipality_name,
        "municipality_name_upper": attrs.get("NA2"),
        "municipality_code": str(municipality_code) if municipality_code is not None else None,
        "boundary_code": attrs.get("COD"),
    }
