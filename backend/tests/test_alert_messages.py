from __future__ import annotations

import unittest

from services.alert_messages import build_whatsapp_risk_alert, should_send_risk_alert


def base_risk(**overrides):
    risk = {
        "crop": "frijol",
        "risk_level": "PREVENIR",
        "confidence": "media_alta",
        "horizon": "1_3_days",
        "plant_state": {"crop": "frijol", "phase": "Floracion/cuajado"},
        "geo_context": {"municipality": "San Salvador", "canton": None},
        "climate_state": {
            "rain": "lluvia muy baja",
            "temperature": "calurosa",
            "seasonal": "vigilancia_canicula",
            "canicula_watch": True,
        },
        "forecast_weather": {"soil_moisture_model": "baja"},
        "risk_factors": [
            {"id": "water_deficit", "state": "deficit relevante"},
            {"id": "heat_stress", "state": "calor alto"},
        ],
    }
    risk.update(overrides)
    return risk


class AlertMessageTests(unittest.TestCase):
    def test_only_prevenir_and_critico_are_notifiable(self):
        self.assertFalse(should_send_risk_alert({"risk_level": "NORMAL"}))
        self.assertFalse(should_send_risk_alert({"risk_level": "ATENCION"}))
        self.assertTrue(should_send_risk_alert({"risk_level": "PREVENIR"}))
        self.assertTrue(should_send_risk_alert({"risk_level": "CRITICO"}))

        with self.assertRaises(ValueError):
            build_whatsapp_risk_alert(base_risk(risk_level="ATENCION"))

    def test_high_alert_uses_assessment_fields_without_technical_terms(self):
        message = build_whatsapp_risk_alert(base_risk())

        self.assertIn("🌱 Buen día", message)
        self.assertIn("productor de San Salvador", message)
        self.assertIn("su frijol", message)
        self.assertIn("fase estimada de floración o formación del fruto", message)
        self.assertIn("poca lluvia esperada", message)
        self.assertIn("calor fuerte", message)
        self.assertIn("vigilancia por canícula", message)
        self.assertIn("señal de posible suelo seco", message)
        self.assertIn("Revise el estado", message)
        self.assertNotIn("media_alta", message)
        self.assertNotIn("Floracion/cuajado", message)
        self.assertNotIn("water_deficit", message)
        self.assertNotIn("estación", message.lower())

    def test_critical_alert_uses_urgent_template_and_actions(self):
        message = build_whatsapp_risk_alert(base_risk(risk_level="CRITICO"))

        self.assertIn("🌡️ Alerta urgente", message)
        self.assertIn("riesgo crítico preventivo por falta de agua", message)
        self.assertIn("calor fuerte", message)
        self.assertIn("Priorice el riego", message)
        self.assertIn("No fertilice", message)
        self.assertIn("No confirma daño", message)

    def test_canton_is_preferred_over_municipality(self):
        message = build_whatsapp_risk_alert(
            base_risk(geo_context={"municipality": "San Salvador", "canton": "El Carmen"})
        )

        self.assertIn("productor de El Carmen", message)
        self.assertNotIn("productor de San Salvador", message)

    def test_missing_zone_does_not_render_none(self):
        message = build_whatsapp_risk_alert(base_risk(geo_context={}))

        self.assertIn("Buen día, productor.", message)
        self.assertNotIn("None", message)

    def test_future_scenario_footer_uses_uncertainty_language(self):
        message = build_whatsapp_risk_alert(base_risk(horizon="gt_16_days", confidence="baja"))

        self.assertIn("escenario preventivo", message)
        self.assertIn("no un pronóstico exacto", message)
        self.assertNotIn("confianza baja", message)

    def test_maize_phase_is_simplified_for_producers(self):
        message = build_whatsapp_risk_alert(
            base_risk(
                crop="maiz",
                plant_state={"crop": "maiz", "phase": "Llenado de grano"},
            )
        )

        self.assertIn("su maíz", message)
        self.assertIn("fase estimada de llenado de mazorca", message)


if __name__ == "__main__":
    unittest.main()
