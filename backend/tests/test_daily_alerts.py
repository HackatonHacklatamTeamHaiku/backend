from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from services.daily_alerts import run_daily_risk_alerts
from services.zavu_notifications import ZavuSendResult


def crop_row(crop_code="maize", crop_id="crop-1"):
    return {
        "user_crop_id": crop_id,
        "profile_id": "profile-1",
        "sowing_date": date(2026, 4, 1),
        "lat": Decimal("13.690000"),
        "lon": Decimal("-89.210000"),
        "crop_code": crop_code,
        "whatsapp_phone": "+50361478494",
        "alert_whatsapp_enabled": True,
    }


def risk(level="PREVENIR"):
    return {
        "crop": "maiz",
        "risk_level": level,
        "confidence": "media",
        "horizon": "present",
        "plant_state": {"crop": "maiz", "phase": "Ventana critica probable de floracion"},
        "geo_context": {"municipality": "San Salvador"},
        "climate_state": {
            "rain": "lluvia baja",
            "temperature": "calurosa",
            "seasonal": "normal_con_vigilancia_canicula",
            "canicula_watch": True,
        },
        "forecast_weather": {"soil_moisture_model": "baja"},
        "risk_factors": [{"id": "water_deficit", "state": "deficit relevante"}],
    }


class DailyAlertsTests(unittest.TestCase):
    @patch("services.daily_alerts.ZavuNotificationClient")
    @patch("services.daily_alerts.get_risk_assessment")
    @patch("services.daily_alerts._fetch_active_user_crops")
    def test_dry_run_builds_message_without_sending(self, fetch_rows, get_risk, zavu_client):
        fetch_rows.return_value = [crop_row()]
        get_risk.return_value = (risk("PREVENIR"), {}, 200)

        result = run_daily_risk_alerts(target_date="2026-05-17", dry_run=True)

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["notifiable"], 1)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["items"][0]["reason"], "dry_run")
        self.assertIn("message_preview", result["items"][0])
        zavu_client.assert_not_called()

    @patch("services.daily_alerts.ZavuNotificationClient")
    @patch("services.daily_alerts.get_risk_assessment")
    @patch("services.daily_alerts._fetch_active_user_crops")
    def test_non_notifiable_risk_is_skipped(self, fetch_rows, get_risk, zavu_client):
        fetch_rows.return_value = [crop_row()]
        get_risk.return_value = (risk("ATENCION"), {}, 200)

        result = run_daily_risk_alerts(target_date="2026-05-17", dry_run=True)

        self.assertEqual(result["notifiable"], 0)
        self.assertEqual(result["items"][0]["action"], "skipped")
        self.assertEqual(result["items"][0]["reason"], "risk_not_notifiable")
        zavu_client.assert_not_called()

    @patch("services.daily_alerts.ZavuNotificationClient")
    @patch("services.daily_alerts.get_risk_assessment")
    @patch("services.daily_alerts._fetch_active_user_crops")
    def test_notifiable_risk_sends_whatsapp(self, fetch_rows, get_risk, zavu_client):
        fetch_rows.return_value = [crop_row(crop_id="crop-123")]
        get_risk.return_value = (risk("CRITICO"), {}, 200)
        client = Mock()
        client.send_whatsapp_text.return_value = ZavuSendResult(
            ok=True,
            provider="zavu",
            message_id="msg-1",
            status="queued",
        )
        zavu_client.return_value = client

        result = run_daily_risk_alerts(target_date="2026-05-17", dry_run=False)

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 0)
        client.send_whatsapp_text.assert_called_once()
        kwargs = client.send_whatsapp_text.call_args.kwargs
        self.assertEqual(kwargs["to"], "+50361478494")
        self.assertEqual(kwargs["idempotency_key"], "daily-risk:crop-123:2026-05-17:whatsapp")

    @patch("services.daily_alerts.ZavuNotificationClient")
    @patch("services.daily_alerts.get_risk_assessment")
    @patch("services.daily_alerts._fetch_active_user_crops")
    def test_zavu_duplicate_is_skipped_not_failed(self, fetch_rows, get_risk, zavu_client):
        fetch_rows.return_value = [crop_row()]
        get_risk.return_value = (risk("PREVENIR"), {}, 200)
        client = Mock()
        client.send_whatsapp_text.return_value = ZavuSendResult(
            ok=False,
            provider="zavu",
            error="Error code: 409 - duplicate",
        )
        zavu_client.return_value = client

        result = run_daily_risk_alerts(target_date="2026-05-17", dry_run=False)

        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["items"][0]["reason"], "duplicate_idempotency_key")


if __name__ == "__main__":
    unittest.main()
