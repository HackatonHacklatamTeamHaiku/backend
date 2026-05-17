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
    archive_crop_cycle,
    create_crop_cycle,
    list_crop_cycles,
    rename_crop_cycle,
)
from utils.time import now_utc_iso

bp = Blueprint("crops", __name__, url_prefix="/api/crops")


@bp.route("", methods=["GET"])
def list_crops():
    profile_id = _current_profile_id()
    if not profile_id:
        return invalid_request("Authenticated user is required")

    return jsonify(_envelope(list_crop_cycles(profile_id)))


@bp.route("", methods=["POST"])
def create_crop():
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
        crop_name = _parse_optional_name(payload.get("crop_name"))
        _validate_supported_location(lat, lon)
    except ValueError as exc:
        return invalid_request(str(exc))

    crop_cycle = create_crop_cycle(
        profile_id=profile_id,
        crop=crop,
        sowing_date=sowing_date,
        lat=lat,
        lon=lon,
        crop_name=crop_name,
    )
    return jsonify(_envelope(crop_cycle))


@bp.route("/<crop_cycle_id>", methods=["PATCH"])
def rename_crop(crop_cycle_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return invalid_request("JSON body is required")

    profile_id = _current_profile_id()
    if not profile_id:
        return invalid_request("Authenticated user is required")

    try:
        crop_name = _parse_required_name(payload.get("crop_name"))
    except ValueError as exc:
        return invalid_request(str(exc))

    crop_cycle = rename_crop_cycle(
        profile_id=profile_id,
        crop_cycle_id=crop_cycle_id,
        crop_name=crop_name,
    )
    if not crop_cycle:
        return invalid_request("Crop was not found")
    return jsonify(_envelope(crop_cycle))


@bp.route("/<crop_cycle_id>", methods=["DELETE"])
def archive_crop(crop_cycle_id: str):
    profile_id = _current_profile_id()
    if not profile_id:
        return invalid_request("Authenticated user is required")

    archived = archive_crop_cycle(profile_id=profile_id, crop_cycle_id=crop_cycle_id)
    if not archived:
        return invalid_request("Crop was not found")
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
        raise ValueError("crop_name is required")
    name = " ".join(value.strip().split())
    if len(name) > 80:
        raise ValueError("crop_name must be 80 characters or fewer")
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
