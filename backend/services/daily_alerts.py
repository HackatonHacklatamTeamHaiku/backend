"""Daily WhatsApp risk alert job."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from services.alert_messages import build_whatsapp_risk_alert, should_send_risk_alert
from services.database import get_dict_cursor
from services.manifest_context import get_risk_assessment
from services.zavu_notifications import ZavuNotificationClient


EL_SALVADOR_TZ = ZoneInfo("America/El_Salvador")
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
    with get_dict_cursor() as cur:
        cur.execute(
            """
            select
                uc.id::text as user_crop_id,
                uc.profile_id::text as profile_id,
                uc.sowing_date,
                uc.lat,
                uc.lon,
                ct.code::text as crop_code,
                p.whatsapp_phone,
                coalesce(up.alert_whatsapp_enabled, true) as alert_whatsapp_enabled
            from user_crops uc
            join profiles p on p.id = uc.profile_id
            join crop_types ct on ct.id = uc.crop_type_id
            left join user_preferences up on up.profile_id = uc.profile_id
            where uc.status = 'active'
              and p.whatsapp_phone is not null
              and p.whatsapp_phone <> ''
              and coalesce(up.alert_whatsapp_enabled, true) = true
            order by uc.created_at asc
            limit %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


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
            assessment, _meta, status = get_risk_assessment(
                {
                    "crop": crop,
                    "sowing_date": row["sowing_date"].isoformat(),
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
