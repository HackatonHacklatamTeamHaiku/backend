from __future__ import annotations

import re

from flask import Blueprint, g, jsonify, request

from routes.request_validation import invalid_request
from services.database import get_dict_cursor
from utils.time import now_utc_iso

bp = Blueprint("profile", __name__, url_prefix="/api/profile")

_PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]{7,30}$")


@bp.route("", methods=["PATCH"])
def update_profile():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return invalid_request("JSON body is required")

    current_user = getattr(g, "current_user", None) or {}
    profile_id = current_user.get("user_id")
    if not profile_id:
        return invalid_request("Authenticated user is required")

    try:
        whatsapp_phone = _parse_optional_phone(payload.get("whatsapp_phone"))
    except ValueError as exc:
        return invalid_request(str(exc))

    with get_dict_cursor() as cur:
        cur.execute(
            """
            UPDATE profiles
            SET whatsapp_phone = %s
            WHERE id = %s
            RETURNING *
            """,
            (whatsapp_phone, profile_id),
        )
        profile = cur.fetchone()

    if not profile:
        return invalid_request("Profile was not found")

    return jsonify(
        {
            "data": dict(profile),
            "meta": {
                "cached": False,
                "stale": False,
                "upstream_status": "ok",
                "fetched_at": now_utc_iso(),
            },
        }
    )


def _parse_optional_phone(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("whatsapp_phone must be a string or null")

    phone = " ".join(value.strip().split())
    if not phone:
        return None
    if not _PHONE_PATTERN.match(phone):
        raise ValueError("whatsapp_phone must be 7-30 characters and use only numbers, spaces, +, -, or parentheses")
    return phone
