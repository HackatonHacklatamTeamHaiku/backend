from __future__ import annotations

import unittest
from unittest.mock import patch

from app import create_app


class InternalJobsRouteTests(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config["CRON_SECRET"] = "test-secret"
        self.client = app.test_client()

    def test_daily_alerts_requires_auth(self):
        response = self.client.post("/api/internal/jobs/daily-risk-alerts", json={})

        self.assertEqual(response.status_code, 401)
        body = response.get_json()
        self.assertEqual(body["meta"]["upstream_status"], "unauthorized")

    def test_daily_alerts_rejects_wrong_secret(self):
        response = self.client.post(
            "/api/internal/jobs/daily-risk-alerts",
            headers={"Authorization": "Bearer wrong"},
            json={},
        )

        self.assertEqual(response.status_code, 401)

    @patch("routes.internal_jobs.run_daily_risk_alerts")
    def test_daily_alerts_runs_with_defaults(self, run_job):
        run_job.return_value = {
            "target_date": "2026-05-17",
            "dry_run": False,
            "limit": 500,
            "processed": 0,
            "notifiable": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "items": [],
        }

        response = self.client.post(
            "/api/internal/jobs/daily-risk-alerts",
            headers={"Authorization": "Bearer test-secret"},
            json={},
        )

        self.assertEqual(response.status_code, 200)
        run_job.assert_called_once_with(target_date=None, dry_run=False, limit=500)

    @patch("routes.internal_jobs.run_daily_risk_alerts")
    def test_daily_alerts_supports_dry_run(self, run_job):
        run_job.return_value = {
            "target_date": "2026-05-17",
            "dry_run": True,
            "limit": 500,
            "processed": 1,
            "notifiable": 1,
            "sent": 0,
            "failed": 0,
            "skipped": 1,
            "items": [],
        }

        response = self.client.post(
            "/api/internal/jobs/daily-risk-alerts",
            headers={"Authorization": "Bearer test-secret"},
            json={"dry_run": True},
        )

        self.assertEqual(response.status_code, 200)
        run_job.assert_called_once_with(target_date=None, dry_run=True, limit=500)
        self.assertTrue(response.get_json()["data"]["dry_run"])


if __name__ == "__main__":
    unittest.main()
