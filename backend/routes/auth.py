from __future__ import annotations

from flask import Blueprint, jsonify, g

from services.parcel_persistence import get_active_parcel_context
from utils.time import now_utc_iso

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/me")
def auth_me():
    current_user = getattr(g, "current_user", None) or {}
    user_id = current_user.get("user_id")
    active_parcel = None
    if user_id:
        try:
            active_parcel = get_active_parcel_context(user_id)
        except Exception:
            active_parcel = None
    return jsonify(
        {
            "data": {
                "user_id": user_id,
                "email": current_user.get("email"),
                "role": current_user.get("role"),
                "claims": current_user.get("claims"),
                "profile": current_user.get("profile"),
                "active_parcel": active_parcel,
            },
            "meta": {
                "cached": False,
                "stale": False,
                "upstream_status": "ok",
                "fetched_at": now_utc_iso(),
            },
        }
    )
