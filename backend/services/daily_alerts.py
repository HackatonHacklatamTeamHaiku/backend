"""Daily WhatsApp risk alert job."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.alert_messages import build_whatsapp_risk_alert, should_send_risk_alert
from services.manifest_context import get_risk_assessment
from services.supabase_rest import rest_select
from services.zavu_notifications import ZavuNotificationClient


try:
    EL_SALVADOR_TZ = ZoneInfo("America/El_Salvador")
except ZoneInfoNotFoundError:
    EL_SALVADOR_TZ = timezone(timedelta(hours=-6), "America/El_Salvador")
DEFAULT_LIMIT = 500
CROP_CODE_MAP = {
    "maize": "maiz",
    "bean": "frijol",
}


def _today() -> date:
    return datetime.now(EL_SALVADOR_TZ).date()


def _parse_target_date(value: str | None) -> date:
    if not value:
        return _today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("target_date must use YYYY-MM-DD format") from exc


def _as_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _crop_from_db(code: str) -> str:
    try:
        return CROP_CODE_MAP[code]
    except KeyError as exc:
        raise ValueError(f"unsupported crop code: {code}") from exc


def _idempotency_key(user_crop_id: str, target_date: date) -> str:
    return f"daily-risk:{user_crop_id}:{target_date.isoformat()}:whatsapp"


def _fetch_active_user_crops(limit: int) -> list[dict]:
    rows = rest_select(
        "user_crops",
        {
            "select": "id,profile_id,sowing_date,lat,lon,crop_type_id,created_at",
            "status": "eq.active",
            "order": "created_at.asc",
            "limit": str(limit),
        },
    )
    active_rows = []
    for row in rows:
        profile = _first(
            rest_select(
                "profiles",
                {"select": "whatsapp_phone", "id": f"eq.{row['profile_id']}", "limit": "1"},
            )
        )
        whatsapp_phone = (profile or {}).get("whatsapp_phone")
        if not whatsapp_phone:
            continue

        preferences = _first(
            rest_select(
                "user_preferences",
                {"select": "alert_whatsapp_enabled", "profile_id": f"eq.{row['profile_id']}", "limit": "1"},
            )
        )
        if preferences and preferences.get("alert_whatsapp_enabled") is False:
            continue

        crop_type = _first(
            rest_select(
                "crop_types",
                {"select": "code", "id": f"eq.{row['crop_type_id']}", "limit": "1"},
            )
        )
        if not crop_type:
            continue

        active_rows.append(
            {
                "user_crop_id": str(row["id"]),
                "profile_id": str(row["profile_id"]),
                "sowing_date": row["sowing_date"],
                "lat": row["lat"],
                "lon": row["lon"],
                "crop_code": crop_type["code"],
                "whatsapp_phone": whatsapp_phone,
                "alert_whatsapp_enabled": True,
            }
        )
    return active_rows


def _first(rows: list[dict]) -> dict | None:
    return rows[0] if rows else None


def _new_summary(target_date: date, dry_run: bool, limit: int) -> dict:
    return {
        "target_date": target_date.isoformat(),
        "dry_run": dry_run,
        "limit": limit,
        "processed": 0,
        "notifiable": 0,
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "items": [],
    }


def _record_item(summary: dict, item: dict) -> None:
    summary["items"].append(item)
    action = item.get("action")
    if action == "sent":
        summary["sent"] += 1
    elif action == "failed":
        summary["failed"] += 1
    else:
        summary["skipped"] += 1


def run_daily_risk_alerts(
    *,
    target_date: str | None = None,
    dry_run: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    """Evaluate active user crops and send daily WhatsApp alerts when needed."""

    if limit <= 0:
        raise ValueError("limit must be greater than 0")
    limit = min(limit, DEFAULT_LIMIT)
    parsed_target_date = _parse_target_date(target_date)
    summary = _new_summary(parsed_target_date, dry_run, limit)
    zavu = None if dry_run else ZavuNotificationClient()

    for row in _fetch_active_user_crops(limit):
        summary["processed"] += 1
        base_item = {
            "user_crop_id": row["user_crop_id"],
            "profile_id": row["profile_id"],
            "whatsapp_phone": row["whatsapp_phone"],
        }
        try:
            crop = _crop_from_db(row["crop_code"])
            sowing_date = _as_date_string(row["sowing_date"])
            if date.fromisoformat(sowing_date) > parsed_target_date:
                _record_item(
                    summary,
                    {
                        **base_item,
                        "crop": crop,
                        "action": "skipped",
                        "reason": "crop_not_started",
                    },
                )
                continue

            assessment, _meta, status = get_risk_assessment(
                {
                    "crop": crop,
                    "sowing_date": sowing_date,
                    "lat": _as_float(row["lat"]),
                    "lon": _as_float(row["lon"]),
                    "target_date": parsed_target_date.isoformat(),
                }
            )
            base_item["crop"] = crop
            if status != 200:
                _record_item(
                    summary,
                    {
                        **base_item,
                        "action": "failed",
                        "reason": "risk_assessment_failed",
                        "error": assessment.get("error", "risk assessment failed"),
                    },
                )
                continue

            risk_level = assessment.get("risk_level")
            base_item["risk_level"] = risk_level
            if not should_send_risk_alert(assessment):
                _record_item(
                    summary,
                    {
                        **base_item,
                        "action": "skipped",
                        "reason": "risk_not_notifiable",
                    },
                )
                continue

            summary["notifiable"] += 1
            message = build_whatsapp_risk_alert(assessment)
            idempotency_key = _idempotency_key(row["user_crop_id"], parsed_target_date)

            if dry_run:
                _record_item(
                    summary,
                    {
                        **base_item,
                        "action": "skipped",
                        "reason": "dry_run",
                        "idempotency_key": idempotency_key,
                        "message_preview": message,
                    },
                )
                continue

            assert zavu is not None
            result = zavu.send_whatsapp_text(
                to=row["whatsapp_phone"],
                text=message,
                idempotency_key=idempotency_key,
            )
            if result.ok:
                _record_item(
                    summary,
                    {
                        **base_item,
                        "action": "sent",
                        "idempotency_key": idempotency_key,
                        "zavu_message_id": result.message_id,
                        "zavu_status": result.status,
                    },
                )
            elif result.error and "Error code: 409" in result.error:
                _record_item(
                    summary,
                    {
                        **base_item,
                        "action": "skipped",
                        "reason": "duplicate_idempotency_key",
                        "idempotency_key": idempotency_key,
                    },
                )
            else:
                _record_item(
                    summary,
                    {
                        **base_item,
                        "action": "failed",
                        "reason": "zavu_send_failed",
                        "idempotency_key": idempotency_key,
                        "error": result.error,
                    },
                )
        except Exception as exc:
            _record_item(
                summary,
                {
                    **base_item,
                    "action": "failed",
                    "reason": "unexpected_error",
                    "error": str(exc),
                },
            )

    return summary


def _as_date_string(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
