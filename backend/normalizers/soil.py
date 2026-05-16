"""
Normalize soil organic matter summaries into coarse water-retention modifiers.
"""

from __future__ import annotations


def soil_modifier_for_label(label: str | None) -> str:
    normalized = (label or "").strip().lower()
    if any(token in normalized for token in ("alto", "muy alto")):
        return "favorable"
    if any(token in normalized for token in ("bajo", "muy bajo")):
        return "unfavorable"
    return "neutral"


def normalize_soil_features(raw_json: dict) -> list[dict]:
    rows: list[dict] = []
    for feature in raw_json.get("features", []):
        attrs = feature.get("attributes") or {}
        municipality_code = attrs.get("First_COD_MUN4")
        if not municipality_code:
            continue
        class_label = attrs.get("First_mo_txt_descrip")
        rows.append(
            {
                "source": "snet_servicio_suelos_pais",
                "municipality_code": str(municipality_code),
                "soil_property": "organic_matter",
                "class_label": class_label,
                "coverage_percent": attrs.get("Sum_porc_"),
                "water_retention_modifier": soil_modifier_for_label(class_label),
            }
        )
    return rows
