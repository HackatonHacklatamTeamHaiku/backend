from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path

from normalizers.risk import build_assessment


LAB_SAMPLES = Path(__file__).parent / "fixtures" / "risk_validation_samples.json"


class RiskEngineTests(unittest.TestCase):
    def test_lab_samples_stay_plausible(self):
        payload = json.loads(LAB_SAMPLES.read_text(encoding="utf-8"))
        reference_date = date(2026, 5, 16)

        for sample in payload["results"]:
            plant_state = sample["plant_state"]
            climate_state = sample["climate_state"]
            days_after_sowing = plant_state["days_after_sowing"]
            target_date = reference_date.fromordinal(reference_date.toordinal() + days_after_sowing)
            sowing_date = reference_date
            request_payload = {
                "crop": plant_state["crop"],
                "sowing_date": sowing_date.isoformat(),
                "target_date": target_date.isoformat(),
                "lat": 13.69,
                "lon": -89.21,
                "rain_sum_mm": climate_state["rain_sum_mm"],
                "et0_sum_mm": climate_state["et0_sum_mm"],
                "days_window": climate_state["days_window"],
                "dry_days": climate_state["dry_days"],
                "temp_max_c": climate_state["temp_max_c"],
                "wind_max_kmh": climate_state["wind_max_kmh"],
                "et0_mm_day": climate_state["et0_mm_day"],
                "soil": climate_state["soil"],
                "seasonal": climate_state["seasonal"],
                "canicula_watch": climate_state["canicula_watch"],
            }

            assessment = build_assessment(request_payload, reference_date=reference_date)
            self.assertEqual(assessment.risk_level, sample["risk_level"])
            self.assertAlmostEqual(assessment.risk_score, sample["risk_score"], places=3)

    def test_reproductive_floor_promotes_attention_to_prevenir(self):
        assessment = build_assessment(
            {
                "crop": "maiz",
                "sowing_date": "2026-05-01",
                "target_date": "2026-07-10",
                "lat": 13.69,
                "lon": -89.21,
                "rain_sum_mm": 10.0,
                "et0_sum_mm": 18.0,
                "days_window": 3,
                "dry_days": 2,
                "temp_max_c": 36.0,
                "wind_max_kmh": 16.0,
                "et0_mm_day": 4.5,
                "soil": "neutral",
                "seasonal": "normal",
                "canicula_watch": False,
            },
            reference_date=date(2026, 7, 8),
        )

        self.assertEqual(assessment.risk_level_base, "ATENCION")
        self.assertEqual(assessment.risk_level, "PREVENIR")
        self.assertEqual(assessment.risk_overrides[0].id, "CRITICAL_PHASE_FLOOR")

    def test_done_phase_does_not_recommend_active_management(self):
        assessment = build_assessment(
            {
                "crop": "frijol",
                "sowing_date": "2026-02-20",
                "target_date": "2026-05-16",
                "lat": 13.69,
                "lon": -89.21,
                "rain_sum_mm": 0.0,
                "et0_sum_mm": 5.0,
                "days_window": 1,
                "dry_days": 1,
                "temp_max_c": 33.0,
                "wind_max_kmh": 20.0,
                "et0_mm_day": 5.0,
                "soil": "neutral",
                "seasonal": "normal",
                "canicula_watch": False,
            },
            reference_date=date(2026, 5, 16),
        )

        self.assertEqual(assessment.plant_state.phase_code, "DONE")
        joined = " ".join(assessment.recommendations)
        self.assertIn("Ciclo cerrado", joined)
        self.assertNotIn("Aportar agua", joined)
        self.assertNotIn("fertilizar", joined)

    def test_normal_level_uses_monitoring_recommendation_only(self):
        assessment = build_assessment(
            {
                "crop": "maiz",
                "sowing_date": "2026-05-01",
                "target_date": "2026-05-16",
                "lat": 13.69,
                "lon": -89.21,
                "rain_sum_mm": 20.0,
                "et0_sum_mm": 5.0,
                "days_window": 1,
                "dry_days": 0,
                "temp_max_c": 28.0,
                "wind_max_kmh": 10.0,
                "et0_mm_day": 3.5,
                "soil": "favorable",
                "seasonal": "normal",
                "canicula_watch": False,
            },
            reference_date=date(2026, 5, 16),
        )

        self.assertEqual(assessment.risk_level, "NORMAL")
        self.assertEqual(assessment.recommendations, ["Mantener monitoreo normal."])

    def test_maturity_heavy_rain_alert_adds_harvest_recommendation(self):
        assessment = build_assessment(
            {
                "crop": "maiz",
                "sowing_date": "2026-02-09",
                "target_date": "2026-05-16",
                "lat": 13.69,
                "lon": -89.21,
                "rain_sum_mm": 30.0,
                "et0_sum_mm": 6.0,
                "days_window": 1,
                "dry_days": 0,
                "temp_max_c": 29.0,
                "wind_max_kmh": 12.0,
                "et0_mm_day": 3.5,
                "soil": "neutral",
                "seasonal": "normal",
                "canicula_watch": False,
            },
            reference_date=date(2026, 5, 16),
        )

        self.assertEqual(assessment.climate_state.rain, "lluvia fuerte")
        self.assertEqual(assessment.secondary_alerts[0].id, "EXCESO_LLUVIA_COSECHA")
        self.assertTrue(any("lluvia fuerte" in item for item in assessment.recommendations))


if __name__ == "__main__":
    unittest.main()
