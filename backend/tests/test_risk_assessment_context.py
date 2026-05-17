from __future__ import annotations

import unittest
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import patch

bs4_stub = types.ModuleType("bs4")
bs4_stub.BeautifulSoup = object
sys.modules.setdefault("bs4", bs4_stub)

from services import manifest_context
from utils.time import EL_SALVADOR_TZ


def make_open_meteo_raw(start_date, days=17):
    dates = [(start_date + timedelta(days=idx)).isoformat() for idx in range(days)]
    return {
        "daily": {
            "time": dates,
            "precipitation_sum": [0.2, 0.0, 2.5, 4.0, 0.0, 1.0, 6.0, 0.5, 0.0, 2.0, 3.0, 0.0, 0.2, 5.0, 1.2, 0.0, 2.0],
            "et0_fao_evapotranspiration_sum": [4.5, 4.0, 4.2, 4.4, 4.1, 4.3, 4.6, 4.8, 4.7, 4.1, 4.2, 4.0, 4.5, 4.4, 4.3, 4.9, 4.2],
            "temperature_2m_max": [31, 32, 34, 33, 35, 32, 31, 36, 34, 33, 32, 31, 35, 36, 32, 33, 34],
            "wind_speed_10m_max": [12, 16, 18, 20, 22, 15, 14, 24, 21, 19, 17, 16, 20, 23, 18, 17, 16],
            "precipitation_probability_max": [10] * days,
            "temperature_2m_min": [22] * days,
        },
        "hourly": {},
    }


class RiskAssessmentContextTests(unittest.TestCase):
    def test_weather_observed_falls_back_to_open_meteo_for_missing_snet_fields(self):
        now = datetime.now(EL_SALVADOR_TZ)
        today = now.date()
        raw = make_open_meteo_raw(today)
        raw["hourly"] = {
            "time": [now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")],
            "temperature_2m": [28.4],
            "relative_humidity_2m": [74],
            "wind_speed_10m": [7.2],
            "wind_direction_10m": [135],
            "precipitation": [0.0],
        }

        with patch.object(manifest_context, "_get_observations") as observations, \
            patch.object(manifest_context, "_get_rainfall") as rainfall, \
            patch.object(manifest_context, "_get_forecast") as forecast:
            observations.return_value = (
                [
                    {
                        "station_id": 61,
                        "station_name": "UES",
                        "lat": 13.69,
                        "lon": -89.21,
                        "temperature": {"current_c": None, "max_c": None, "min_c": None},
                        "wind": {"speed": None, "direction_deg": None},
                        "observed_at_local": None,
                        "sources_used": ["snet_temperatura_actual_max_min"],
                    }
                ],
                False,
                "2026-05-17T00:00:00Z",
            )
            rainfall.return_value = (
                [
                    {
                        "station_id": 264,
                        "station_name": "Zoologico",
                        "lat": 13.69,
                        "lon": -89.21,
                        "rain_mm_period": None,
                        "is_raining": None,
                        "obs_time_latest_local": None,
                    }
                ],
                False,
                "2026-05-17T00:00:00Z",
            )
            forecast.return_value = (raw, False, "2026-05-17T00:00:00Z")

            data, meta = manifest_context.get_weather_observed(13.69, -89.21)

        self.assertEqual(data["temperature_current_c"], 28.4)
        self.assertEqual(data["temperature_max_c"], 31.0)
        self.assertEqual(data["temperature_min_c"], 22.0)
        self.assertEqual(data["rain_recent_mm"], 0.2)
        self.assertEqual(data["humidity_relative_percent"], 74.0)
        self.assertEqual(data["wind_speed_kmh"], 7.2)
        self.assertEqual(data["wind_direction_deg"], 135.0)
        self.assertEqual(data["field_sources"]["temperature_current_c"], "open_meteo_forecast")
        self.assertEqual(data["field_sources"]["rain_recent_mm"], "open_meteo_forecast")
        self.assertEqual(data["field_sources"]["humidity_relative_percent"], "open_meteo_forecast")
        self.assertEqual(data["field_sources"]["wind_direction_deg"], "open_meteo_forecast")
        self.assertIn("open_meteo_forecast", data["fallback_sources"])
        self.assertEqual(meta["upstream_status"], "degraded")

    def test_forecast_window_summary_uses_tomorrow_to_target(self):
        today = datetime.now(EL_SALVADOR_TZ).date()
        raw = make_open_meteo_raw(today)
        target = today + timedelta(days=3)

        summary = manifest_context._forecast_window_summary(raw, today, target)

        self.assertEqual(summary["days_window"], 3)
        self.assertEqual(summary["forecast_window"]["start"], (today + timedelta(days=1)).isoformat())
        self.assertEqual(summary["forecast_window"]["end"], target.isoformat())
        self.assertAlmostEqual(summary["rain_sum_mm"], 6.5)
        self.assertAlmostEqual(summary["et0_sum_mm"], 12.6)
        self.assertEqual(summary["dry_days"], 1)
        self.assertEqual(summary["temp_max_c"], 34)
        self.assertEqual(summary["wind_max_kmh"], 20)

    def test_risk_assessment_future_uses_window_without_fallback_assumptions(self):
        today = datetime.now(EL_SALVADOR_TZ).date()
        raw = make_open_meteo_raw(today)
        target = today + timedelta(days=3)

        with patch.object(manifest_context, "get_weather_observed") as observed, \
            patch.object(manifest_context, "get_weather_forecast") as forecast, \
            patch.object(manifest_context, "get_geo_context") as geo, \
            patch.object(manifest_context, "get_official_context") as official, \
            patch.object(manifest_context, "_get_forecast") as raw_forecast:
            observed.return_value = ({"warnings": [], "sources_used": []}, {"stale": False, "fetched_at": "2026-05-16T00:00:00Z"})
            forecast.return_value = ({"warnings": [], "sources_used": ["open_meteo_forecast"]}, {"stale": False, "fetched_at": "2026-05-16T00:00:00Z"})
            geo.return_value = (
                {
                    "soil_context": {"water_retention_modifier": "neutral"},
                    "climate_outlook_context": {"dryness_prior": "normal"},
                    "warnings": [],
                    "sources_used": [],
                },
                {"stale": False, "fetched_at": "2026-05-16T00:00:00Z"},
            )
            official.return_value = {"canicula_2026_watch": False, "sources_used": []}
            raw_forecast.return_value = (raw, False, "2026-05-16T00:00:00Z")

            data, _, status = manifest_context.get_risk_assessment(
                {
                    "crop": "maiz",
                    "sowing_date": today.isoformat(),
                    "lat": 13.69,
                    "lon": -89.21,
                    "target_date": target.isoformat(),
                }
            )

        self.assertEqual(status, 200)
        self.assertEqual(data["climate_state"]["days_window"], 3)
        self.assertAlmostEqual(data["climate_state"]["rain_sum_mm"], 6.5)
        self.assertEqual(data["climate_state"]["dry_days"], 1)
        self.assertFalse(any("rain_sum_mm no estaba disponible" in item for item in data["assumptions"]))
        self.assertTrue(any("Forecast agregado" in item for item in data["derived_inputs"]))

    def test_plus_one_day_is_labeled_as_forecast_window(self):
        today = datetime.now(EL_SALVADOR_TZ).date()
        raw = make_open_meteo_raw(today)
        target = today + timedelta(days=1)

        with patch.object(manifest_context, "get_weather_observed") as observed, \
            patch.object(manifest_context, "get_weather_forecast") as forecast, \
            patch.object(manifest_context, "get_geo_context") as geo, \
            patch.object(manifest_context, "get_official_context") as official, \
            patch.object(manifest_context, "_get_forecast") as raw_forecast:
            observed.return_value = (
                {"warnings": [], "sources_used": ["snet_lluvia_data_24h", "snet_temperatura_actual_max_min"]},
                {"stale": False, "fetched_at": "2026-05-16T00:00:00Z"},
            )
            forecast.return_value = ({"warnings": [], "sources_used": ["open_meteo_forecast"]}, {"stale": False, "fetched_at": "2026-05-16T00:00:00Z"})
            geo.return_value = (
                {
                    "soil_context": {"water_retention_modifier": "neutral"},
                    "climate_outlook_context": {"dryness_prior": "normal"},
                    "warnings": [],
                    "sources_used": ["snet_servicio_suelos_pais"],
                },
                {"stale": False, "fetched_at": "2026-05-16T00:00:00Z"},
            )
            official.return_value = {"canicula_2026_watch": False, "sources_used": []}
            raw_forecast.return_value = (raw, False, "2026-05-16T00:00:00Z")

            data, _, status = manifest_context.get_risk_assessment(
                {
                    "crop": "maiz",
                    "sowing_date": today.isoformat(),
                    "lat": "13.69",
                    "lon": "-89.21",
                    "target_date": target.isoformat(),
                }
            )

        self.assertEqual(status, 200)
        self.assertEqual(data["risk_window_weather"]["source_type"], "forecast_window")
        self.assertIn("open_meteo_forecast", data["source_roles"]["scoring_sources"])
        self.assertNotIn("snet_lluvia_data_24h", data["source_roles"]["scoring_sources"])

    def test_gt_16_days_uses_seasonal_scenario_not_rain_zero_forecast(self):
        today = datetime.now(EL_SALVADOR_TZ).date()
        target = today + timedelta(days=20)

        assessment = manifest_context.build_assessment(
            {
                "crop": "maiz",
                "sowing_date": today.isoformat(),
                "target_date": target.isoformat(),
                "lat": 13.69,
                "lon": -89.21,
                "soil": "neutral",
                "seasonal": "bajo_lo_normal",
                "canicula_watch": True,
                "scenario_mode": "seasonal",
                "days_window": 20,
                "input_warnings": ["Para >16 dias no hay pronostico puntual."],
            },
            reference_date=today,
        )

        self.assertEqual(assessment.horizon, "gt_16_days")
        self.assertEqual(assessment.confidence, "baja")
        self.assertEqual(assessment.climate_state.rain, "escenario estacional")
        self.assertIsNone(assessment.climate_state.rain_sum_mm)
        self.assertFalse(any("rain_sum_mm no estaba disponible" in item for item in assessment.assumptions))
        self.assertFalse(any("et0_sum_mm no estaba disponible" in item for item in assessment.assumptions))

    def test_invalid_request_values_return_400_without_calling_sources(self):
        cases = [
            {
                "crop": "maiz",
                "sowing_date": "2026-05-01",
                "lat": "abc",
                "lon": "-89.21",
                "target_date": datetime.now(EL_SALVADOR_TZ).date().isoformat(),
            },
            {
                "crop": "maiz",
                "sowing_date": "2026-05-01",
                "lat": "nan",
                "lon": "-89.21",
                "target_date": datetime.now(EL_SALVADOR_TZ).date().isoformat(),
            },
            {
                "crop": "maiz",
                "sowing_date": "2026-05-01",
                "lat": "999",
                "lon": "999",
                "target_date": datetime.now(EL_SALVADOR_TZ).date().isoformat(),
            },
            {
                "crop": "maiz",
                "sowing_date": "2026-05-01",
                "lat": "13.69",
                "lon": "-89.21",
                "target_date": "2026-99-99",
            },
            {
                "crop": "maiz",
                "sowing_date": "2026-05-01",
                "lat": "13.69",
                "lon": "-89.21",
                "target_date": (datetime.now(EL_SALVADOR_TZ).date() - timedelta(days=1)).isoformat(),
            },
        ]

        for query in cases:
            data, meta, status = manifest_context.get_risk_assessment(query)
            self.assertEqual(status, 400)
            self.assertIn("error", data)
            self.assertEqual(meta["upstream_status"], "invalid_request")

    def test_plus_16_is_seasonal_boundary_with_current_open_meteo_window(self):
        today = datetime.now(EL_SALVADOR_TZ).date()
        target = today + timedelta(days=16)

        assessment = manifest_context.build_assessment(
            {
                "crop": "maiz",
                "sowing_date": today.isoformat(),
                "target_date": target.isoformat(),
                "lat": 13.69,
                "lon": -89.21,
                "soil": "neutral",
                "seasonal": "normal",
                "canicula_watch": True,
                "scenario_mode": "seasonal",
                "days_window": 20,
            },
            reference_date=today,
        )

        self.assertEqual(assessment.horizon, "gt_16_days")
        self.assertEqual(assessment.confidence, "baja")
        self.assertEqual(assessment.climate_state.rain, "escenario estacional")

    def test_forecast_out_of_range_does_not_return_target_soil_moisture(self):
        today = datetime.now(EL_SALVADOR_TZ).date()
        raw = make_open_meteo_raw(today)
        raw["hourly"] = {
            "soil_moisture_0_to_1cm": [0.1, 0.2],
            "soil_moisture_1_to_3cm": [0.1, 0.2],
            "soil_moisture_3_to_9cm": [0.1, 0.2],
        }

        with patch.object(manifest_context, "_get_forecast", return_value=(raw, False, "2026-05-16T00:00:00Z")):
            data, _ = manifest_context.get_weather_forecast(13.69, -89.21, today + timedelta(days=30))

        self.assertFalse(data["target_in_forecast_range"])
        self.assertIsNone(data["soil_moisture_model"])
        self.assertIsNone(data["soil_moisture_model_scope"])

    def test_llm_explain_mentions_seasonal_scenario_and_secondary_alert(self):
        result = manifest_context.explain_recommendation(
            {
                "risk_assessment": {
                    "risk_level": "PREVENIR",
                    "confidence": "baja",
                    "horizon": "gt_16_days",
                    "climate_state": {"rain": "escenario estacional"},
                    "risk_factors": [{"label": "Deficit hidrico", "state": "deficit relevante"}],
                    "secondary_alerts": [{"message": "Lluvia fuerte durante maduracion/cosecha."}],
                },
                "plant_state": {"phase": "Floracion/polinizacion"},
                "recommendations": ["Monitorear nuevamente en 24-48 horas."],
                "official_context": {"canicula_2026_watch": True},
            }
        )

        self.assertIn("escenario estacional", result["summary"])
        self.assertIn("no un pronostico puntual", result["summary"])
        self.assertIn("Alerta secundaria", result["summary"])

    def test_llm_explain_formats_factor_phrases_without_duplicate_words(self):
        result = manifest_context.explain_recommendation(
            {
                "risk_assessment": {
                    "risk_level": "PREVENIR",
                    "confidence": "alta",
                    "risk_factors": [
                        {"label": "Deficit hidrico", "state": "deficit severo"},
                        {"label": "Calor", "state": "calor critico"},
                        {"label": "Contexto estacional", "state": "vigilancia seca"},
                    ],
                    "secondary_alerts": [],
                },
                "plant_state": {"phase": "Germinacion/emergencia"},
                "recommendations": ["Revisar humedad del suelo."],
                "official_context": {"canicula_2026_watch": True},
            }
        )

        summary = result["summary"]
        self.assertIn("deficit hidrico severo", summary)
        self.assertIn("calor critico", summary)
        self.assertIn("contexto estacional con vigilancia seca", summary)
        self.assertNotIn("deficit hidrico deficit", summary)
        self.assertNotIn("calor calor", summary)

    def test_llm_runtime_context_separates_today_from_selected_target_date(self):
        today = datetime.now(EL_SALVADOR_TZ).date()
        target = today + timedelta(days=14)

        risk_payload = {
            "target_date": target.isoformat(),
            "horizon": "plus_16_days",
            "risk_score": 0.42,
            "risk_level_base": "NORMAL",
            "risk_level": "NORMAL",
            "confidence": "alta",
            "horizon_confidence": "alta",
            "data_quality_confidence": "alta",
            "confidence_reasons": [],
            "plant_state": {
                "days_after_sowing": 14,
                "phase": "Vegetativo",
                "phase_code": "V2_V4",
            },
            "climate_state": {},
            "risk_factors": [],
            "risk_overrides": [],
            "secondary_alerts": [],
            "risk_window_weather": {},
            "observed_weather": {},
            "forecast_weather": {},
            "source_roles": {},
            "derived_inputs": [],
            "assumptions": [],
            "input_warnings": [],
            "recommendations": [],
            "official_context": {},
            "sources_used": [],
        }

        with patch.object(
            manifest_context,
            "get_risk_assessment",
            return_value=(risk_payload, {"upstream_status": "ok"}, 200),
        ):
            context, _, status = manifest_context.build_runtime_llm_context(
                {
                    "crop": "frijol",
                    "sowing_date": today.isoformat(),
                    "lat": 13.69,
                    "lon": -89.21,
                    "target_date": target.isoformat(),
                }
            )

        self.assertEqual(status, 200)
        self.assertEqual(context["current_date"], today.isoformat())
        self.assertEqual(context["temporal_context"]["sowing_date"], today.isoformat())
        self.assertFalse(context["temporal_context"]["is_selected_target_today"])
        self.assertEqual(context["current_plant_state"]["days_after_sowing"], 0)
        self.assertEqual(context["current_plant_state"]["phase"], "Germinacion/emergencia")
        self.assertEqual(context["target_plant_state"]["days_after_sowing"], 14)
        self.assertEqual(context["target_plant_state"]["phase"], "Vegetativo")
        self.assertEqual(context["plant_state"]["days_after_sowing"], 14)
        self.assertIn("Use current_plant_state", context["temporal_context"]["usage_rule"])

    def test_llm_runtime_context_includes_dynamic_crop_calendar_for_supported_crops(self):
        risk_payload = {
            "target_date": "2026-05-24",
            "horizon": "4_7_days",
            "risk_score": 0.42,
            "risk_level_base": "NORMAL",
            "risk_level": "NORMAL",
            "confidence": "alta",
            "horizon_confidence": "alta",
            "data_quality_confidence": "alta",
            "confidence_reasons": [],
            "plant_state": {
                "days_after_sowing": 14,
                "phase": "Vegetativo",
                "phase_code": "V2_V4",
            },
            "climate_state": {},
            "risk_factors": [],
            "risk_overrides": [],
            "secondary_alerts": [],
            "risk_window_weather": {},
            "observed_weather": {},
            "forecast_weather": {},
            "source_roles": {},
            "derived_inputs": [],
            "assumptions": [],
            "input_warnings": [],
            "recommendations": [],
            "official_context": {},
            "sources_used": [],
        }

        cases = [
            ("maiz", "Inicio Llenado de grano"),
            ("frijol", "Inicio Formacion de vainas"),
        ]
        for crop, expected_phase_event in cases:
            with self.subTest(crop=crop), patch.object(
                manifest_context,
                "get_risk_assessment",
                return_value=(risk_payload, {"upstream_status": "ok"}, 200),
            ):
                context, _, status = manifest_context.build_runtime_llm_context(
                    {
                        "crop": crop,
                        "sowing_date": "2026-05-10",
                        "lat": 13.69,
                        "lon": -89.21,
                        "target_date": "2026-05-24",
                        "conversation_started_date": "2026-05-17",
                    }
                )

            self.assertEqual(status, 200)
            calendar = context["crop_calendar"]
            csv_text = calendar["csv"]
            self.assertEqual(calendar["present_date"], "2026-05-17")
            self.assertEqual(calendar["present_days_after_sowing"], 7)
            self.assertIn("Día,Días desde Siembra,Días desde presente,Evento", csv_text)
            self.assertIn("Siembra", csv_text)
            self.assertIn("Presente", csv_text)
            self.assertIn(expected_phase_event, csv_text)
            self.assertNotIn("Codigo", csv_text)
            self.assertTrue(context["phenology_calendar_rules"])

    def test_llm_explain_mentions_degraded_data_quality(self):
        result = manifest_context.explain_recommendation(
            {
                "risk_assessment": {
                    "risk_level": "NORMAL",
                    "confidence": "media_alta",
                    "horizon_confidence": "media_alta",
                    "data_quality_confidence": "media_baja",
                    "assumptions": ["seasonal default"],
                    "input_warnings": ["missing outlook"],
                    "risk_factors": [{"label": "Deficit hidrico", "state": "sin deficit"}],
                    "secondary_alerts": [],
                },
                "plant_state": {"phase": "Vegetativo temprano"},
                "recommendations": ["Mantener monitoreo normal."],
                "official_context": {},
            }
        )

        self.assertIn("confianza de horizonte media_alta", result["summary"])
        self.assertIn("calidad de datos media_baja", result["summary"])
        self.assertIn("supuestos o advertencias", result["summary"])


if __name__ == "__main__":
    unittest.main()
