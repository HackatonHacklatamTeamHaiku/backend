from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from routes.request_validation import invalid_request
from services.manifest_context import (
    _parse_coordinate,
    _parse_request_date,
    _validate_supported_location,
)
from services.parcel_persistence import (
    CROP_CODE_TO_ID,
    archive_plant_cycle,
    create_plant_cycle,
    list_crop_cycles,
    rename_plant_cycle,
)
from utils.time import now_utc_iso

bp = Blueprint("plants", __name__, url_prefix="/api/plants")


@bp.route("", methods=["GET"])
def list_plants():
    profile_id = _current_profile_id()
    if not profile_id:
        return invalid_request("Authenticated user is required")

    return jsonify(_envelope(list_crop_cycles(profile_id)))


@bp.route("", methods=["POST"])
def create_plant():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return invalid_request("JSON body is required")

    profile_id = _current_profile_id()
    if not profile_id:
        return invalid_request("Authenticated user is required")

    try:
        crop = _parse_crop(payload.get("crop"))
        sowing_date = _parse_body_date(payload.get("sowing_date"), "sowing_date")
        lat = _parse_coordinate(payload.get("lat"), "lat")
        lon = _parse_coordinate(payload.get("lon"), "lon")
        plant_name = _parse_optional_name(payload.get("plant_name") or payload.get("crop_name"))
        _validate_supported_location(lat, lon)
    except ValueError as exc:
        return invalid_request(str(exc))

    plant = create_plant_cycle(
        profile_id=profile_id,
        crop=crop,
        sowing_date=sowing_date,
        lat=lat,
        lon=lon,
        plant_name=plant_name,
    )
    return jsonify(_envelope(plant))


@bp.route("/<crop_cycle_id>", methods=["PATCH"])
def rename_plant(crop_cycle_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return invalid_request("JSON body is required")

    profile_id = _current_profile_id()
    if not profile_id:
        return invalid_request("Authenticated user is required")

    try:
        plant_name = _parse_required_name(payload.get("plant_name") or payload.get("crop_name"))
    except ValueError as exc:
        return invalid_request(str(exc))

    plant = rename_plant_cycle(
        profile_id=profile_id,
        crop_cycle_id=crop_cycle_id,
        plant_name=plant_name,
    )
    if not plant:
        return invalid_request("Plant was not found")
    return jsonify(_envelope(plant))


@bp.route("/<crop_cycle_id>", methods=["DELETE"])
def archive_plant(crop_cycle_id: str):
    profile_id = _current_profile_id()
    if not profile_id:
        return invalid_request("Authenticated user is required")

    archived = archive_plant_cycle(profile_id=profile_id, crop_cycle_id=crop_cycle_id)
    if not archived:
        return invalid_request("Plant was not found")
    return jsonify(_envelope(archived))


def _current_profile_id() -> str | None:
    current_user = getattr(g, "current_user", None) or {}
    return current_user.get("user_id")


def _parse_crop(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("crop is required")
    crop = value.strip().lower()
    if crop not in CROP_CODE_TO_ID:
        raise ValueError("crop must be maiz or frijol")
    return crop


def _parse_body_date(value, field: str):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return _parse_request_date(value, field)


def _parse_optional_name(value) -> str | None:
    if value is None:
        return None
    return _parse_required_name(value)


def _parse_required_name(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("plant_name is required")
    name = " ".join(value.strip().split())
    if len(name) > 80:
        raise ValueError("plant_name must be 80 characters or fewer")
    return name


def _envelope(data):
    return {
        "data": data,
        "meta": {
            "cached": False,
            "stale": False,
            "upstream_status": "ok",
            "fetched_at": now_utc_iso(),
        },
    }
