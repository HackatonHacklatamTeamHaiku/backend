from __future__ import annotations

from flask import jsonify

from utils.time import now_utc_iso


def invalid_request(message: str):
    return jsonify(
        {
            "data": {"error": message},
            "meta": {
                "cached": False,
                "stale": False,
                "upstream_status": "invalid_request",
                "fetched_at": now_utc_iso(),
            },
        }
    ), 400


def repeated_param_error(args, fields: list[str]):
    for field in fields:
        if len(args.getlist(field)) > 1:
            return f"{field} query parameter must not be repeated"
    return None


def empty_param_error(args, fields: list[str]):
    for field in fields:
        if field in args and args.get(field) == "":
            return f"{field} query parameter must not be empty"
    return None
