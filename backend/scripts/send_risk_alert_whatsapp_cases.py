from __future__ import annotations

import argparse
import copy
import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
sys.path.insert(0, str(ROOT))

from services.alert_messages import build_whatsapp_risk_alert, should_send_risk_alert  # noqa: E402
from services.manifest_context import get_risk_assessment  # noqa: E402
from services.zavu_notifications import ZavuNotificationClient  # noqa: E402


EL_SALVADOR_TZ = ZoneInfo("America/El_Salvador")


@dataclass(frozen=True)
class AlertCase:
    name: str
    crop: str
    sowing_date: str
    target_date: str
    lat: float
    lon: float
    template_level: str | None = None


def _iso(day) -> str:
    return day.isoformat()


def _default_cases() -> list[AlertCase]:
    today = datetime.now(EL_SALVADOR_TZ).date()
    seasonal_target = today + timedelta(days=54)
    bean_target = today + timedelta(days=39)

    return [
        AlertCase(
            name="maiz_real_alto_escenario",
            crop="maiz",
            sowing_date=_iso(seasonal_target - timedelta(days=70)),
            target_date=_iso(seasonal_target),
            lat=13.69,
            lon=-89.21,
        ),
        AlertCase(
            name="frijol_real_alto_escenario",
            crop="frijol",
            sowing_date=_iso(bean_target - timedelta(days=36)),
            target_date=_iso(bean_target),
            lat=13.69,
            lon=-89.21,
        ),
        AlertCase(
            name="frijol_critico_plantilla_hoy",
            crop="frijol",
            sowing_date=_iso(today - timedelta(days=40)),
            target_date=_iso(today),
            lat=13.69,
            lon=-89.21,
            template_level="CRITICO",
        ),
        AlertCase(
            name="maiz_alto_plantilla_hoy",
            crop="maiz",
            sowing_date=_iso(today - timedelta(days=63)),
            target_date=_iso(today),
            lat=13.69,
            lon=-89.21,
            template_level="PREVENIR",
        ),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send several WhatsApp alert message cases built from live risk assessments."
    )
    parser.add_argument("--to", default="+50361478494", help="Destination phone in E.164 format")
    parser.add_argument("--send", action="store_true", help="Actually send messages through Zavu")
    parser.add_argument(
        "--only-real-alerts",
        action="store_true",
        help="Skip template-level cases when the live assessment is not PREVENIR/CRITICO",
    )
    parser.add_argument(
        "--force-new",
        action="store_true",
        help="Use a fresh idempotency key suffix so Zavu sends the same preview messages again",
    )
    return parser.parse_args()


def _assessment_for(case: AlertCase) -> dict:
    data, _meta, status = get_risk_assessment(
        {
            "crop": case.crop,
            "sowing_date": case.sowing_date,
            "lat": case.lat,
            "lon": case.lon,
            "target_date": case.target_date,
        }
    )
    if status != 200:
        raise RuntimeError(f"risk assessment failed for {case.name}: {data}")
    return data


def _message_risk(case: AlertCase, assessment: dict, only_real_alerts: bool) -> dict | None:
    if case.template_level and not only_real_alerts:
        message_risk = copy.deepcopy(assessment)
        message_risk["risk_level_actual"] = assessment.get("risk_level")
        message_risk["risk_level"] = case.template_level
        return message_risk

    if should_send_risk_alert(assessment):
        return assessment
    if only_real_alerts:
        return None
    return None


def _idempotency_key(case: AlertCase, to: str, message: str, force_new: bool) -> str:
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:12]
    suffix = f":{datetime.now(EL_SALVADOR_TZ).strftime('%Y%m%d%H%M%S')}" if force_new else ""
    return f"sato-agro:alert-case:{case.name}:{to}:{digest}{suffix}"


def main() -> None:
    load_dotenv(ENV_PATH)
    args = parse_args()
    client = ZavuNotificationClient() if args.send else None
    sent = 0
    skipped = 0

    for index, case in enumerate(_default_cases(), start=1):
        assessment = _assessment_for(case)
        message_risk = _message_risk(case, assessment, args.only_real_alerts)
        actual_level = assessment.get("risk_level")
        template_level = (message_risk or {}).get("risk_level")

        print(f"\n=== CASE {index}: {case.name} ===")
        print(f"crop={case.crop}")
        print(f"sowing_date={case.sowing_date}")
        print(f"target_date={case.target_date}")
        print(f"assessment_risk_level={actual_level}")
        print(f"template_risk_level={template_level or 'SKIPPED'}")
        print(f"phase={(assessment.get('plant_state') or {}).get('phase')}")
        print(f"horizon={assessment.get('horizon')}")

        if not message_risk:
            print("skip_reason=assessment_not_notifiable")
            skipped += 1
            continue

        message = build_whatsapp_risk_alert(message_risk)
        print("--- MESSAGE ---")
        print(message)

        if args.send and client:
            result = client.send_whatsapp_text(
                to=args.to,
                text=message,
                idempotency_key=_idempotency_key(case, args.to, message, args.force_new),
            )
            print("--- ZAVU ---")
            print(f"sent={str(result.ok).lower()}")
            if result.message_id:
                print(f"message_id={result.message_id}")
            if result.status:
                print(f"status={result.status}")
            if result.error:
                print(f"error={result.error}")
            if not result.ok:
                raise SystemExit(1)
            sent += 1

    print("\n=== SUMMARY ===")
    print(f"sent={sent}")
    print(f"skipped={skipped}")
    print(f"send_enabled={str(args.send).lower()}")


if __name__ == "__main__":
    main()
