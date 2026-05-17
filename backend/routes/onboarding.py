from __future__ import annotations

from datetime import date

from flask import Blueprint, g, jsonify, request

from routes.request_validation import invalid_request
from services.manifest_context import (
    _parse_coordinate,
    _parse_request_date,
    _validate_supported_location,
)
from services.parcel_persistence import CROP_CODE_TO_ID, save_onboarding_parcel
from utils.time import now_utc_iso

bp = Blueprint("onboarding", __name__, url_prefix="/api/onboarding")


@bp.route("/parcel", methods=["POST"])
def onboarding_parcel():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return invalid_request("JSON body is required")

    try:
        crop = _parse_crop(payload.get("crop"))
        sowing_date = _parse_body_date(payload.get("sowing_date"), "sowing_date")
        lat = _parse_coordinate(payload.get("lat"), "lat")
        lon = _parse_coordinate(payload.get("lon"), "lon")
        _validate_supported_location(lat, lon)
    except ValueError as exc:
        return invalid_request(str(exc))

    current_user = getattr(g, "current_user", None) or {}
    profile_id = current_user.get("user_id")
    if not profile_id:
        return invalid_request("Authenticated user is required")

    parcel = save_onboarding_parcel(
        profile_id=profile_id,
        crop=crop,
        sowing_date=sowing_date,
        lat=lat,
        lon=lon,
        farm_name=_optional_text(payload.get("farm_name")) or "Finca principal",
        plot_name=_optional_text(payload.get("plot_name")) or "Parcela principal",
    )
    return jsonify(
        {
            "data": parcel,
            "meta": {
                "cached": False,
                "stale": False,
                "upstream_status": "ok",
                "fetched_at": now_utc_iso(),
            },
        }
    )


def _parse_crop(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("crop is required")
    crop = value.strip().lower()
    if crop not in CROP_CODE_TO_ID:
        raise ValueError("crop must be maiz or frijol")
    return crop


def _parse_body_date(value, field: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return _parse_request_date(value, field)


def _optional_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
