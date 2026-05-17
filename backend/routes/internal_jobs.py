from __future__ import annotations

from hmac import compare_digest

from flask import Blueprint, current_app, jsonify, request

from services.daily_alerts import DEFAULT_LIMIT, run_daily_risk_alerts
from utils.time import now_utc_iso


bp = Blueprint("internal_jobs", __name__, url_prefix="/api/internal/jobs")


def _meta(upstream_status: str) -> dict:
    return {
        "cached": False,
        "stale": False,
        "upstream_status": upstream_status,
        "fetched_at": now_utc_iso(),
    }


def _json_error(message: str, status_code: int, upstream_status: str):
    return jsonify({"data": {"error": message}, "meta": _meta(upstream_status)}), status_code


def _authorized() -> bool:
    secret = current_app.config.get("CRON_SECRET") or ""
    if not secret:
        return False
    header = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not header.startswith(prefix):
        return False
    token = header[len(prefix):].strip()
    return bool(token) and compare_digest(token, secret)


@bp.route("/daily-risk-alerts", methods=["POST"])
def daily_risk_alerts():
    if not current_app.config.get("CRON_SECRET"):
        return _json_error("CRON_SECRET is not configured", 503, "configuration_error")
    if not _authorized():
        return _json_error("unauthorized", 401, "unauthorized")

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _json_error("request body must be a JSON object", 400, "invalid_request")

    dry_run = bool(payload.get("dry_run", False))
    target_date = payload.get("target_date")
    limit = payload.get("limit", DEFAULT_LIMIT)
    try:
        limit = int(limit)
        data = run_daily_risk_alerts(
            target_date=target_date,
            dry_run=dry_run,
            limit=limit,
        )
    except ValueError as exc:
        return _json_error(str(exc), 400, "invalid_request")
    except RuntimeError as exc:
        return _json_error(str(exc), 503, "configuration_error")

    upstream_status = "ok" if data.get("failed", 0) == 0 else "degraded"
    return jsonify({"data": data, "meta": _meta(upstream_status)}), 200
