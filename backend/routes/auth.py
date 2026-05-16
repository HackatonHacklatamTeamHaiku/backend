from __future__ import annotations

from flask import Blueprint, jsonify, g

from utils.time import now_utc_iso

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/me")
def auth_me():
    current_user = getattr(g, "current_user", None) or {}
    return jsonify(
        {
            "data": {
                "user_id": current_user.get("user_id"),
                "email": current_user.get("email"),
                "role": current_user.get("role"),
                "claims": current_user.get("claims"),
                "profile": current_user.get("profile"),
            },
            "meta": {
                "cached": False,
                "stale": False,
                "upstream_status": "ok",
                "fetched_at": now_utc_iso(),
            },
        }
    )
