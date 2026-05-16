"""
MVP agroclimatic risk engine for maize and bean advisory.

This module lifts the documented formulas from the research lab into the
normalized backend layer so routes and AI tools can reuse one transparent
implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from models.schemas import (
    AgroRiskAssessment,
    ClimateState,
    PlantState,
    PlantSusceptibility,
    RiskFactorDetail,
    RiskOverride,
    SecondaryAlert,
)


WEIGHTS = {
    "water_deficit": 0.40,
    "heat_stress": 0.20,
    "evap_stress": 0.10,
    "soil_factor": 0.15,
    "seasonal_factor": 0.15,
}

HORIZON_CONFIDENCE = {
    "present": "alta",
    "1_3_days": "media_alta",
    "4_7_days": "media",
    "8_16_days": "media_baja",
    "gt_16_days": "baja",
}

SOIL_FACTORS = {
    "favorable": 0.2,
    "neutral": 0.5,
    "unfavorable": 1.0,
}

SEASONAL_BASE = {
    "arriba_lo_normal": 0.1,
    "normal": 0.3,
    "bajo_lo_normal": 0.7,
    "canicula_o_sequia_fuerte": 1.0,
}

SUSCEPTIBILITY = {
    "maiz": {
        "VE": {
            "phase": "Germinacion/emergencia",
            "water": 1.00,
            "heat": 0.60,
            "evaporation": 0.60,
            "soil": 0.85,
            "seasonal": 0.50,
        },
        "V1_V6": {
            "phase": "Vegetativo temprano",
            "water": 0.60,
            "heat": 0.50,
            "evaporation": 0.50,
            "soil": 0.70,
            "seasonal": 0.50,
        },
        "V7_VT": {
            "phase": "Vegetativo avanzado/prefloracion",
            "water": 0.85,
            "heat": 0.70,
            "evaporation": 0.70,
            "soil": 0.75,
            "seasonal": 0.70,
        },
        "VT_R1": {
            "phase": "Ventana critica probable de floracion",
            "water": 1.00,
            "heat": 1.00,
            "evaporation": 0.85,
            "soil": 0.75,
            "seasonal": 0.85,
        },
        "R2_R4": {
            "phase": "Llenado de grano",
            "water": 0.85,
            "heat": 0.80,
            "evaporation": 0.70,
            "soil": 0.65,
            "seasonal": 0.65,
        },
        "R5_R6": {
            "phase": "Maduracion",
            "water": 0.40,
            "heat": 0.40,
            "evaporation": 0.40,
            "soil": 0.40,
            "seasonal": 0.30,
        },
        "DONE": {
            "phase": "Cosecha/ciclo cerrado",
            "water": 0.20,
            "heat": 0.20,
            "evaporation": 0.20,
            "soil": 0.20,
            "seasonal": 0.20,
        },
    },
    "frijol": {
        "V0_V1": {
            "phase": "Germinacion/emergencia",
            "water": 1.00,
            "heat": 0.70,
            "evaporation": 0.60,
            "soil": 0.85,
            "seasonal": 0.50,
        },
        "V2_V4": {
            "phase": "Vegetativo",
            "water": 0.60,
            "heat": 0.60,
            "evaporation": 0.50,
            "soil": 0.70,
            "seasonal": 0.50,
        },
        "R5": {
            "phase": "Preparando floracion",
            "water": 0.85,
            "heat": 0.85,
            "evaporation": 0.70,
            "soil": 0.75,
            "seasonal": 0.70,
        },
        "R6": {
            "phase": "Floracion/cuajado",
            "water": 1.00,
            "heat": 1.00,
            "evaporation": 0.85,
            "soil": 0.75,
            "seasonal": 0.85,
        },
        "R7": {
            "phase": "Formacion de vainas",
            "water": 1.00,
            "heat": 0.90,
            "evaporation": 0.80,
            "soil": 0.75,
            "seasonal": 0.85,
        },
        "R8": {
            "phase": "Llenado de grano",
            "water": 0.85,
            "heat": 0.80,
            "evaporation": 0.70,
            "soil": 0.65,
            "seasonal": 0.65,
        },
        "R9": {
            "phase": "Maduracion",
            "water": 0.40,
            "heat": 0.40,
            "evaporation": 0.40,
            "soil": 0.40,
            "seasonal": 0.30,
        },
        "DONE": {
            "phase": "Cosecha/ciclo cerrado",
            "water": 0.20,
            "heat": 0.20,
            "evaporation": 0.20,
            "soil": 0.20,
            "seasonal": 0.20,
        },
    },
}

FACTOR_META = {
    "water_deficit": (
        "Deficit hidrico",
        "Lluvia acumulada baja frente a demanda atmosferica y persistencia de dias secos.",
    ),
    "heat_stress": (
        "Calor",
        "Temperatura maxima cercana o superior al umbral operativo del cultivo.",
    ),
    "evap_stress": (
        "Evaporacion/viento",
        "Viento o ET0 diarios apuntan a secado rapido del sistema suelo-planta.",
    ),
    "soil_factor": (
        "Suelo",
        "El contexto de suelo modifica cuanta lluvia puede convertirse en agua util para la raiz.",
    ),
    "seasonal_factor": (
        "Contexto estacional",
        "El prior estacional aumenta la vigilancia cuando el entorno apunta a deficit o canicula.",
    ),
}

FACTOR_STATE_LABELS = {
    "water_deficit": [
        (0.8, "deficit severo"),
        (0.5, "deficit relevante"),
        (0.25, "deficit leve"),
        (0.0, "sin deficit relevante"),
    ],
    "heat_stress": [
        (0.8, "calor critico"),
        (0.5, "calor alto"),
        (0.25, "calor moderado"),
        (0.0, "sin calor relevante"),
    ],
    "evap_stress": [
        (0.8, "secado rapido severo"),
        (0.5, "secado rapido"),
        (0.25, "demanda evaporativa moderada"),
        (0.0, "sin secado rapido relevante"),
    ],
    "soil_factor": [
        (0.8, "suelo desfavorable"),
        (0.4, "suelo neutral"),
        (0.0, "suelo favorable"),
    ],
    "seasonal_factor": [
        (0.85, "canicula o sequia fuerte"),
        (0.5, "vigilancia seca"),
        (0.25, "estacional neutral"),
        (0.0, "estacional favorable"),
    ],
}


@dataclass
class RiskInputs:
    crop: str
    sowing_date: date
    target_date: date
    lat: float
    lon: float
    rain_sum_mm: float
    et0_sum_mm: float
    days_window: int
    dry_days: int
    temp_max_c: float
    wind_max_kmh: float
    et0_mm_day: float
    soil: str
    seasonal: str
    canicula_watch: bool
    sources_used: list[str]
    assumptions: list[str]
    input_warnings: list[str]


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def infer_horizon(reference_date: date, target_date: date) -> str:
    delta_days = (target_date - reference_date).days
    if delta_days <= 0:
        return "present"
    if delta_days <= 3:
        return "1_3_days"
    if delta_days <= 7:
        return "4_7_days"
    if delta_days <= 16:
        return "8_16_days"
    return "gt_16_days"


def default_days_window(horizon: str) -> int:
    if horizon == "present":
        return 1
    if horizon == "1_3_days":
        return 3
    if horizon == "4_7_days":
        return 7
    if horizon == "8_16_days":
        return 16
    return 20


def phase_for(crop: str, days: int) -> tuple[str, dict]:
    if crop == "maiz":
        if days <= 7:
            code = "VE"
        elif days <= 35:
            code = "V1_V6"
        elif days <= 60:
            code = "V7_VT"
        elif days <= 80:
            code = "VT_R1"
        elif days <= 95:
            code = "R2_R4"
        elif days <= 120:
            code = "R5_R6"
        else:
            code = "DONE"
    elif crop == "frijol":
        if days <= 7:
            code = "V0_V1"
        elif days <= 30:
            code = "V2_V4"
        elif days <= 34:
            code = "R5"
        elif days <= 40:
            code = "R6"
        elif days <= 55:
            code = "R7"
        elif days <= 65:
            code = "R8"
        elif days <= 75:
            code = "R9"
        else:
            code = "DONE"
    else:
        raise ValueError(f"Unsupported crop: {crop}")
    return code, SUSCEPTIBILITY[crop][code]


def seasonal_factor(base_name: str, canicula_watch: bool) -> float:
    if base_name == "canicula_o_sequia_fuerte":
        return 1.0
    return clamp(SEASONAL_BASE[base_name] + (0.2 if canicula_watch else 0.0))


def risk_level(score: float) -> str:
    if score < 0.25:
        return "NORMAL"
    if score < 0.50:
        return "ATENCION"
    if score < 0.75:
        return "PREVENIR"
    return "CRITICO"


def normalize_risk_inputs(
    payload: dict,
    *,
    reference_date: date,
) -> RiskInputs:
    crop = (payload.get("crop") or "").strip().lower()
    if crop not in {"maiz", "frijol"}:
        raise ValueError("crop must be 'maiz' or 'frijol'")

    target_date_raw = payload.get("target_date")
    target_date = parse_iso_date(target_date_raw) if target_date_raw else reference_date
    sowing_date = parse_iso_date(payload["sowing_date"])
    horizon = infer_horizon(reference_date, target_date)
    days_window = int(payload.get("days_window") or default_days_window(horizon))

    assumptions = list(payload.get("assumptions") or [])
    input_warnings = list(payload.get("input_warnings") or [])

    rain_sum_mm = payload.get("rain_sum_mm")
    if rain_sum_mm is None:
        rain_sum_mm = 0.0
        assumptions.append(
            "rain_sum_mm no estaba disponible en el backend; se asumio 0.0 mm hasta integrar lluvia observada/pronosticada."
        )

    et0_sum_mm = payload.get("et0_sum_mm")
    if et0_sum_mm is None:
        et0_sum_mm = max(days_window * 4.0, 1.0)
        assumptions.append(
            "et0_sum_mm no estaba disponible; se estimo con una demanda base de 4.0 mm/dia para no bloquear el motor MVP."
        )

    dry_days = payload.get("dry_days")
    if dry_days is None:
        dry_days = days_window if rain_sum_mm < 1.0 else 0
        assumptions.append(
            "dry_days no estaba disponible; se infirio desde rain_sum_mm usando el criterio operativo < 1 mm."
        )

    temp_max_c = payload.get("temp_max_c")
    if temp_max_c is None:
        raise ValueError("temp_max_c is required or must be derivable from canonical observations")

    wind_max_kmh = payload.get("wind_max_kmh")
    if wind_max_kmh is None:
        raise ValueError("wind_max_kmh is required or must be derivable from canonical observations")

    et0_mm_day = payload.get("et0_mm_day")
    if et0_mm_day is None:
        et0_mm_day = round(et0_sum_mm / max(days_window, 1), 2)
        assumptions.append(
            "et0_mm_day no estaba disponible; se derivo como et0_sum_mm / days_window."
        )

    soil = (payload.get("soil") or "neutral").strip().lower()
    if soil not in SOIL_FACTORS:
        raise ValueError("soil must be one of favorable, neutral, unfavorable")
    if payload.get("soil") is None:
        assumptions.append(
            "soil no estaba integrado con servicio territorial; se uso 'neutral' como modificador conservador."
        )

    seasonal = (payload.get("seasonal") or "normal").strip().lower()
    if seasonal not in SEASONAL_BASE:
        raise ValueError(
            "seasonal must be one of arriba_lo_normal, normal, bajo_lo_normal, canicula_o_sequia_fuerte"
        )
    if payload.get("seasonal") is None:
        assumptions.append(
            "seasonal no estaba integrado con perspectivas mensuales; se uso 'normal' como prior base."
        )

    canicula_watch = bool(payload.get("canicula_watch", False))
    if payload.get("canicula_watch") is None:
        assumptions.append(
            "canicula_watch no estaba integrado con contexto oficial vigente; se uso false por defecto."
        )

    return RiskInputs(
        crop=crop,
        sowing_date=sowing_date,
        target_date=target_date,
        lat=float(payload["lat"]),
        lon=float(payload["lon"]),
        rain_sum_mm=float(rain_sum_mm),
        et0_sum_mm=float(et0_sum_mm),
        days_window=days_window,
        dry_days=int(dry_days),
        temp_max_c=float(temp_max_c),
        wind_max_kmh=float(wind_max_kmh),
        et0_mm_day=float(et0_mm_day),
        soil=soil,
        seasonal=seasonal,
        canicula_watch=canicula_watch,
        sources_used=list(payload.get("sources_used") or []),
        assumptions=assumptions,
        input_warnings=input_warnings,
    )


def calculate_factors(inputs: RiskInputs) -> dict[str, float]:
    dry_days_ratio = inputs.dry_days / max(inputs.days_window, 1)
    water_deficit = (
        0.7 * max(0.0, inputs.et0_sum_mm - inputs.rain_sum_mm) / max(inputs.et0_sum_mm, 1.0)
        + 0.3 * dry_days_ratio
    )

    if inputs.crop == "maiz":
        temp_warning, temp_critical = 33.0, 38.0
    else:
        temp_warning, temp_critical = 30.0, 35.0
    heat_stress = clamp((inputs.temp_max_c - temp_warning) / (temp_critical - temp_warning))

    wind_score = clamp((inputs.wind_max_kmh - 15.0) / (35.0 - 15.0))
    et0_score = clamp((inputs.et0_mm_day - 4.0) / (7.0 - 4.0))
    evap_stress = max(wind_score, et0_score)

    return {
        "water_deficit": clamp(water_deficit),
        "heat_stress": heat_stress,
        "evap_stress": evap_stress,
        "soil_factor": SOIL_FACTORS[inputs.soil],
        "seasonal_factor": seasonal_factor(inputs.seasonal, inputs.canicula_watch),
    }


def state_label(factor_id: str, value: float) -> str:
    for threshold, label in FACTOR_STATE_LABELS[factor_id]:
        if value >= threshold:
            return label
    return FACTOR_STATE_LABELS[factor_id][-1][1]


def factor_objects(factors: dict[str, float], plant: dict) -> list[RiskFactorDetail]:
    susceptibility_key = {
        "water_deficit": "water",
        "heat_stress": "heat",
        "evap_stress": "evaporation",
        "soil_factor": "soil",
        "seasonal_factor": "seasonal",
    }
    details: list[RiskFactorDetail] = []
    for factor_id, value in factors.items():
        plant_key = susceptibility_key[factor_id]
        label, evidence = FACTOR_META[factor_id]
        contribution = round(WEIGHTS[factor_id] * value * plant[plant_key], 4)
        details.append(
            RiskFactorDetail(
                id=factor_id,
                label=label,
                climate_value=round(value, 4),
                plant_susceptibility=plant[plant_key],
                weight=WEIGHTS[factor_id],
                contribution=contribution,
                state=state_label(factor_id, value),
                evidence=evidence,
            )
        )
    return sorted(details, key=lambda item: item.contribution, reverse=True)


def climate_state_labels(inputs: RiskInputs) -> ClimateState:
    rain_label = "sin lluvia"
    if inputs.rain_sum_mm > 30:
        rain_label = "lluvia fuerte"
    elif inputs.rain_sum_mm > 10:
        rain_label = "lluvia potencialmente util"
    elif inputs.rain_sum_mm > 2:
        rain_label = "lluvia baja a moderada"
    elif inputs.rain_sum_mm > 0:
        rain_label = "lluvia muy baja"

    if inputs.crop == "maiz":
        temp_warning, temp_critical = 33.0, 38.0
    else:
        temp_warning, temp_critical = 30.0, 35.0
    if inputs.temp_max_c >= temp_critical:
        temperature_label = "calor critico"
    elif inputs.temp_max_c >= temp_warning:
        temperature_label = "calurosa"
    else:
        temperature_label = "estable"

    if inputs.wind_max_kmh >= 35 or inputs.et0_mm_day >= 7:
        evap_label = "alto"
    elif inputs.wind_max_kmh >= 15 or inputs.et0_mm_day >= 4:
        evap_label = "moderado"
    else:
        evap_label = "bajo"

    seasonal_label = inputs.seasonal
    if inputs.canicula_watch and inputs.seasonal != "canicula_o_sequia_fuerte":
        seasonal_label = "vigilancia_canicula"

    return ClimateState(
        rain=rain_label,
        temperature=temperature_label,
        wind_evaporation=evap_label,
        soil=inputs.soil,
        seasonal=seasonal_label,
        rain_sum_mm=round(inputs.rain_sum_mm, 2),
        et0_sum_mm=round(inputs.et0_sum_mm, 2),
        days_window=inputs.days_window,
        dry_days=inputs.dry_days,
        temp_max_c=round(inputs.temp_max_c, 2),
        wind_max_kmh=round(inputs.wind_max_kmh, 2),
        et0_mm_day=round(inputs.et0_mm_day, 2),
        canicula_watch=inputs.canicula_watch,
    )


def build_recommendations(
    *,
    level: str,
    factors: list[RiskFactorDetail],
    phase_code: str,
    rain_sum_mm: float,
    temp_max_c: float,
    crop: str,
) -> list[str]:
    actions: list[str] = []
    dominant = factors[0].id if factors else None

    if dominant == "water_deficit" or level in {"PREVENIR", "CRITICO"}:
        actions.append("Revisar humedad del suelo.")
        actions.append("Aportar agua si es posible.")

    if any(item.id == "evap_stress" and item.climate_value >= 0.5 for item in factors):
        actions.append("Mantener cobertura y evitar aplicaciones con viento.")

    heat_warning = 33.0 if crop == "maiz" else 30.0
    if temp_max_c >= heat_warning:
        actions.append("Evitar fertilizar o aplicar insumos en horas calientes.")

    if rain_sum_mm < 1.0:
        actions.append("Conservar humedad y revisar signos de marchitez.")

    if phase_code in {"VT_R1", "R6", "R7"} and level in {"PREVENIR", "CRITICO"}:
        actions.append("Priorizar monitoreo tecnico por fase critica.")

    if not actions:
        actions.append("Mantener monitoreo normal.")

    if level in {"ATENCION", "PREVENIR"}:
        actions.append("Monitorear nuevamente en 24-48 horas.")
    elif level == "CRITICO":
        actions.append("Actuar hoy y volver a revisar la parcela en las proximas 24 horas.")

    seen: set[str] = set()
    deduped: list[str] = []
    for action in actions:
        if action not in seen:
            seen.add(action)
            deduped.append(action)
    return deduped


def apply_risk_overrides(
    *,
    crop: str,
    phase_code: str,
    risk_level_base: str,
    water_deficit: float,
    heat_stress: float,
    rain_sum_mm: float,
    plant_phase: str,
) -> tuple[str, list[RiskOverride], list[SecondaryAlert]]:
    level = risk_level_base
    overrides: list[RiskOverride] = []
    secondary_alerts: list[SecondaryAlert] = []

    critical_phase = (
        (crop == "maiz" and phase_code == "VT_R1")
        or (crop == "frijol" and phase_code in {"R6", "R7"})
    )
    if critical_phase and (water_deficit >= 0.60 or heat_stress >= 0.60) and level == "ATENCION":
        level = "PREVENIR"
        overrides.append(
            RiskOverride(
                id="CRITICAL_PHASE_FLOOR",
                reason="Fase reproductiva critica con deficit hidrico o calor relevante.",
            )
        )

    if rain_sum_mm >= 30 and phase_code in {"R5_R6", "R9", "DONE"}:
        secondary_alerts.append(
            SecondaryAlert(
                id="EXCESO_LLUVIA_COSECHA",
                level="ATENCION",
                message=(
                    "Lluvia fuerte durante maduracion/cosecha puede afectar secado, "
                    "cosecha o aumentar riesgo de acame/encharcamiento."
                ),
            )
        )

    if "maduracion" in plant_phase.lower() and rain_sum_mm >= 30 and not secondary_alerts:
        secondary_alerts.append(
            SecondaryAlert(
                id="EXCESO_LLUVIA_COSECHA",
                level="ATENCION",
                message=(
                    "Lluvia fuerte durante maduracion/cosecha puede afectar secado, "
                    "cosecha o aumentar riesgo de acame/encharcamiento."
                ),
            )
        )

    return level, overrides, secondary_alerts


def build_assessment(
    payload: dict,
    *,
    reference_date: date,
) -> AgroRiskAssessment:
    inputs = normalize_risk_inputs(payload, reference_date=reference_date)

    days_after_sowing = (inputs.target_date - inputs.sowing_date).days
    if days_after_sowing < 0:
        raise ValueError("target_date cannot be earlier than sowing_date")

    phase_code, plant = phase_for(inputs.crop, days_after_sowing)
    horizon = infer_horizon(reference_date, inputs.target_date)
    factors = calculate_factors(inputs)
    factor_details = factor_objects(factors, plant)
    score = round(sum(item.contribution for item in factor_details), 4)
    base_level = risk_level(score)
    final_level, overrides, secondary_alerts = apply_risk_overrides(
        crop=inputs.crop,
        phase_code=phase_code,
        risk_level_base=base_level,
        water_deficit=factors["water_deficit"],
        heat_stress=factors["heat_stress"],
        rain_sum_mm=inputs.rain_sum_mm,
        plant_phase=plant["phase"],
    )

    ui_phase_group = None
    if inputs.crop == "frijol" and 41 <= days_after_sowing <= 50:
        ui_phase_group = "Ventana reproductiva critica"

    recommendations = build_recommendations(
        level=final_level,
        factors=factor_details,
        phase_code=phase_code,
        rain_sum_mm=inputs.rain_sum_mm,
        temp_max_c=inputs.temp_max_c,
        crop=inputs.crop,
    )

    return AgroRiskAssessment(
        target_date=inputs.target_date.isoformat(),
        horizon=horizon,
        confidence=HORIZON_CONFIDENCE[horizon],
        plant_state=PlantState(
            crop=inputs.crop,
            days_after_sowing=days_after_sowing,
            phase=plant["phase"],
            phase_code=phase_code,
            ui_phase_group=ui_phase_group,
            susceptibility=PlantSusceptibility(
                water=plant["water"],
                heat=plant["heat"],
                evaporation=plant["evaporation"],
                soil=plant["soil"],
                seasonal=plant["seasonal"],
            ),
        ),
        climate_state=climate_state_labels(inputs),
        risk_factors=factor_details,
        risk_score=score,
        risk_level_base=base_level,
        risk_level=final_level,
        risk_overrides=overrides,
        recommendations=recommendations,
        secondary_alerts=secondary_alerts,
        sources_used=inputs.sources_used,
        assumptions=inputs.assumptions,
        input_warnings=inputs.input_warnings,
    )
