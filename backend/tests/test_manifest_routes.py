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


if __name__ == "__main__":
    unittest.main()
