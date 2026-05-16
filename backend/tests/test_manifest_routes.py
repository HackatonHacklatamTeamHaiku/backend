from __future__ import annotations

import unittest
from unittest.mock import patch

from app import create_app


class ManifestRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app().test_client()

    @patch("routes.weather.get_weather_observed")
    def test_weather_observed_route(self, mocked):
        mocked.return_value = ({"source_type": "observado", "rain_recent_mm": 0.6}, {"cached": True})
        response = self.app.get("/api/weather/observed?lat=13.69&lon=-89.21")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["data"]["source_type"], "observado")
        self.assertEqual(body["data"]["rain_recent_mm"], 0.6)

    def test_weather_routes_reject_invalid_request_values(self):
        cases = [
            "/api/weather/observed?lat=nan&lon=-89.21",
            "/api/weather/observed?lat=12.99&lon=-89.21",
            "/api/weather/observed?lat=13.69%20&lon=-89.21",
            "/api/weather/forecast?lat=13.69&lon=-89.21&target_date=2026-99-99",
            "/api/weather/forecast?lat=13.69&lon=-89.21&target_date=2026-6-1",
            "/api/weather/forecast?lat=13.69&lat=13.7&lon=-89.21",
        ]
        for path in cases:
            response = self.app.get(path)
            self.assertEqual(response.status_code, 400)
            body = response.get_json()
            self.assertEqual(body["meta"]["upstream_status"], "invalid_request")

    def test_geo_route_rejects_invalid_request_values(self):
        response = self.app.get("/api/geo/context?lat=13.69&lon=-89.21&target_date=2026-99-99")
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["meta"]["upstream_status"], "invalid_request")

    def test_llm_context_requires_full_runtime_inputs(self):
        response = self.app.get("/api/llm/context?sowing_date=2026-05-01&lat=13.69&lon=-89.21&target_date=2026-06-01")
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["meta"]["upstream_status"], "invalid_request")

    def test_llm_explain_rejects_malformed_payloads(self):
        cases = [
            {},
            {"risk_assessment": "not-object"},
            {"risk_assessment": {"risk_factors": "bad"}},
            {"risk_assessment": {"risk_factors": ["bad"]}},
            {"risk_assessment": {}, "recommendations": "bad"},
        ]
        for payload in cases:
            response = self.app.post("/api/llm/explain", json=payload)
            self.assertEqual(response.status_code, 400)
            body = response.get_json()
            self.assertEqual(body["meta"]["upstream_status"], "invalid_request")

    def test_llm_explain_accepts_normal_payload(self):
        response = self.app.post(
            "/api/llm/explain",
            json={
                "risk_assessment": {
                    "risk_level": "NORMAL",
                    "confidence": "alta",
                    "risk_factors": [{"label": "Deficit hidrico", "state": "sin deficit"}],
                    "secondary_alerts": [],
                },
                "plant_state": {"phase": "Vegetativo temprano"},
                "recommendations": ["Mantener monitoreo normal."],
                "official_context": {},
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("Vegetativo temprano", body["data"]["summary"])

    @patch("routes.risk.get_risk_assessment")
    def test_risk_assessment_route(self, mocked):
        mocked.return_value = ({"risk_level": "PREVENIR", "confidence": "media"}, {"cached": True}, 200)
        response = self.app.get("/api/risk/assessment?crop=maiz&sowing_date=2026-05-01&lat=13.69&lon=-89.21")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["data"]["risk_level"], "PREVENIR")

    @patch("routes.llm.build_runtime_llm_context")
    def test_llm_context_route(self, mocked):
        mocked.return_value = ({"current_datetime": "2026-05-16T10:30:00-06:00"}, {"cached": True}, 200)
        response = self.app.get("/api/llm/context?crop=frijol&sowing_date=2026-05-01&lat=13.69&lon=-89.21")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("current_datetime", body["data"])

    def test_retired_v1_observations_route_returns_404(self):
        response = self.app.get("/api/v1/observations/current")
        self.assertEqual(response.status_code, 404)

    def test_retired_v1_agro_advisory_route_returns_404(self):
        response = self.app.get("/api/v1/agro/advisory?crop=maiz&sowing_date=2026-05-20&lat=13.69&lon=-89.21")
        self.assertEqual(response.status_code, 404)

    def test_ai_tools_manifest_matches_runtime_model_surface(self):
        response = self.app.get("/api/v1/ai/tools/manifest")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        tool_names = [tool["name"] for tool in body["tools"]]
        self.assertEqual(
            tool_names,
            [
                "getRiskAssessment",
                "getOfficialContext",
                "getPhenologyContext",
                "explainRecommendation",
            ],
        )

    @patch("routes.llm.build_runtime_llm_context")
    def test_llm_context_exposes_runtime_context_keys(self, mocked):
        mocked.return_value = (
            {
                "current_datetime": "2026-05-16T10:30:00-06:00",
                "timezone": "America/El_Salvador",
                "user_inputs": {"crop": "maiz", "sowing_date": "2026-05-20", "lat": 13.69, "lon": -89.21},
                "ui_state": {"selected_target_date": "2026-08-15", "selected_horizon": "8_16_days", "visible_panel": "risk_summary"},
                "missing_required_user_data": [],
                "plant_state": {"phase": "Floracion"},
                "observed_weather": {"source_type": "observado"},
                "forecast_weather": {"source_type": "pronosticado"},
                "risk_assessment": {"risk_level": "ALTO"},
                "recommendations": ["Monitorear"],
                "official_context": {"canicula_2026_watch": True},
                "sources_used": ["open_meteo_forecast"],
                "source_policy": {"observed": "SNET/MARN observado local"},
            },
            {"cached": True},
            200,
        )
        response = self.app.get("/api/llm/context?crop=maiz&sowing_date=2026-05-20&lat=13.69&lon=-89.21&target_date=2026-08-15")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()["data"]
        self.assertIn("missing_required_user_data", body)
        self.assertIn("sources_used", body)


if __name__ == "__main__":
    unittest.main()
