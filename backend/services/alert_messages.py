"""Producer-facing alert message builders."""

from __future__ import annotations


CRITICAL_LEVELS = {"PREVENIR", "CRITICO"}
BANNED_USER_TERMS = {
    "media_alta",
    "media_baja",
    "water_deficit",
    "heat_stress",
    "evap_stress",
    "seasonal_factor",
    "soil_factor",
    "Open-Meteo",
    "backend",
    "estación cercana",
}


def should_send_risk_alert(risk: dict) -> bool:
    return risk.get("risk_level") in CRITICAL_LEVELS


def _crop_label(crop: str | None) -> str:
    return {"maiz": "maíz", "frijol": "frijol"}.get((crop or "").lower(), "cultivo")


def _risk_label(level: str | None) -> str:
    if level == "CRITICO":
        return "CRITICO"
    if level == "PREVENIR":
        return "ALTO"
    return level or "SIN DATO"


def _factor_phrase(factor_id: str | None) -> str | None:
    return {
        "water_deficit": "falta de agua",
        "heat_stress": "calor fuerte",
        "evap_stress": "secado rápido del suelo",
        "seasonal_factor": "canícula",
        "soil_factor": "condición del suelo",
    }.get(factor_id or "")


def _risk_reasons(risk_factors: list[dict], climate: dict) -> str:
    reasons: list[str] = []
    for factor in risk_factors:
        phrase = _factor_phrase(factor.get("id"))
        if phrase and phrase not in reasons:
            reasons.append(phrase)
        if len(reasons) == 2:
            break

    if climate.get("canicula_watch") and "canícula" not in reasons:
        reasons.append("canícula")

    if not reasons:
        return "calor, canícula o falta de agua"
    if len(reasons) == 1:
        return reasons[0]
    return f"{', '.join(reasons[:-1])} y {reasons[-1]}"


def _simple_phase(phase: str | None, crop: str) -> str:
    text = (phase or "").lower()
    if "flor" in text or "poliniz" in text or "cuaj" in text:
        return "floración o formación del fruto"
    if "vaina" in text:
        return "formación de vainas"
    if "llenado" in text and crop == "maíz":
        return "llenado de mazorca"
    if "llenado" in text:
        return "llenado del grano"
    if "germin" in text or "emerg" in text:
        return "nacimiento de la planta"
    if "vegetativo" in text or "preflor" in text:
        return "crecimiento antes de producir"
    if "madur" in text:
        return "maduración"
    if "cosecha" in text or "cerrado" in text:
        return "cosecha o cierre del ciclo"
    return "una etapa sensible"


def _sensitivity_phrase(phase: str) -> str:
    if phase in {"floración o formación del fruto", "formación de vainas"}:
        return "una etapa delicada para la planta"
    if phase in {"llenado de mazorca", "llenado del grano", "nacimiento de la planta"}:
        return "una etapa sensible"
    return "una etapa que necesita vigilancia"


def _weather_sentence(climate: dict, forecast: dict | None = None) -> str:
    rain = (climate.get("rain") or "").lower()
    temperature = (climate.get("temperature") or "").lower()
    seasonal = (climate.get("seasonal") or "").lower()
    soil_moisture = ((forecast or {}).get("soil_moisture_model") or "").lower()
    parts: list[str] = []

    if "sin lluvia" in rain or "muy baja" in rain or "baja" in rain:
        parts.append("poca lluvia esperada")
    if "calor" in temperature or "calurosa" in temperature:
        parts.append("calor fuerte")
    if soil_moisture == "baja":
        parts.append("señal de posible suelo seco")
    if climate.get("canicula_watch") or "canicula" in seasonal:
        parts.append("vigilancia por canícula")

    parts = list(dict.fromkeys(parts))

    if not parts:
        return ""
    if len(parts) == 1:
        return f"Los próximos días requieren cuidado por {parts[0]}."
    return f"Los próximos días requieren cuidado por {', '.join(parts[:-1])} y {parts[-1]}."


def _high_actions() -> list[str]:
    return [
        "Revise el estado de sus plantas en la mañana.",
        "Aproveche cualquier oportunidad de riego o captación de agua.",
        "No aplique productos con el calor fuerte del mediodía.",
    ]


def _critical_actions() -> list[str]:
    return [
        "Priorice el riego sobre cualquier otra labor, si tiene agua disponible.",
        "Cubra el suelo con rastrojo o cobertura para conservar humedad.",
        "No fertilice ni aplique productos mientras el suelo esté muy seco.",
        "Revise en campo hoy mismo.",
    ]


def _footer(risk: dict) -> str:
    if risk.get("horizon") == "gt_16_days":
        return "Esto es un escenario preventivo, no un pronóstico exacto de su parcela. Revise en campo."
    if risk.get("confidence") in {"baja", "media_baja"}:
        return "Esta alerta es preventiva. Úsela como señal para revisar su cultivo en campo."
    return "Esta alerta se basa en datos recientes de su zona. Revise en campo para confirmar."


def build_whatsapp_risk_alert(risk: dict) -> str:
    """Build a concise WhatsApp alert for smallholder producers."""

    if not should_send_risk_alert(risk):
        raise ValueError("risk_level must be PREVENIR or CRITICO to build a WhatsApp alert")

    crop = _crop_label(risk.get("crop") or (risk.get("plant_state") or {}).get("crop"))
    plant = risk.get("plant_state") or {}
    geo = risk.get("geo_context") or {}
    climate = risk.get("climate_state") or {}
    forecast = risk.get("forecast_weather") or {}

    phase = _simple_phase(plant.get("phase"), crop)
    municipality = geo.get("municipality")
    canton = geo.get("canton")
    zone = canton or municipality
    zone_text = f" de {zone}" if zone else ""
    weather = _weather_sentence(climate, forecast)
    reasons = _risk_reasons(risk.get("risk_factors") or [], climate)

    if risk.get("risk_level") == "CRITICO":
        lines = [
            f"🌡️ Alerta urgente SATO-Agro para productor{zone_text}.",
            "",
            f"Su {crop} está en fase estimada de {phase}, {_sensitivity_phrase(phase)}.",
            f"Las condiciones son de riesgo crítico preventivo por {reasons}.",
        ]
        if weather:
            lines.append(weather)
        lines.extend(["", "Lo más importante que puede hacer hoy:"])
        actions = _critical_actions()
    else:
        lines = [
            f"🌱 Buen día, productor{zone_text}.",
            "",
            f"Hemos detectado riesgo preventivo de sequía para su {crop}, que está en fase estimada de {phase}.",
        ]
        if weather:
            lines.append(weather)
        else:
            lines.append("Los próximos días pueden requerir más cuidado por calor o poca lluvia.")
        lines.extend(["", "Acciones recomendadas para hoy:"])
        actions = _high_actions()

    for action in actions:
        lines.append(f"• {action}")

    if risk.get("risk_level") == "CRITICO":
        lines.extend(["", "No confirma daño, pero las condiciones son serias. Actúe hoy y revise en campo."])
    else:
        lines.extend(["", _footer(risk)])

    message = "\n".join(lines)
    for term in BANNED_USER_TERMS:
        if term in message:
            raise ValueError(f"alert message contains technical term: {term}")
    return message
