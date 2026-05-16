"""
Normalize monthly climate outlook point responses.
"""

from __future__ import annotations


def normalize_outlook_feature(raw_json: dict, *, layer_id: int, month_label: str, lat: float, lon: float) -> dict | None:
    features = raw_json.get("features") or []
    if not features:
        return None

    attrs = features[0].get("attributes") or {}
    scenario_label = (attrs.get("Escenario") or "").strip()
    scenario_lower = scenario_label.lower()
    if "bajo" in scenario_lower:
        dryness_prior = "bajo_lo_normal"
    elif "arriba" in scenario_lower:
        dryness_prior = "arriba_lo_normal"
    else:
        dryness_prior = "normal"

    return {
        "source": "snet_perspectivas_clima_servicio",
        "month": month_label,
        "layer_id": layer_id,
        "lat": lat,
        "lon": lon,
        "scenario_code": attrs.get("gridcode"),
        "scenario_label": scenario_label or None,
        "dryness_prior": dryness_prior,
        "temporal_role": "seasonal",
        "current_for_alerting": True,
    }
