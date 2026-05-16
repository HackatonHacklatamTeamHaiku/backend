"""
Composition helpers that align backend responses with the manifest contract.
"""

from __future__ import annotations

from datetime import datetime

from config import Config
from normalizers.basins import basin_for_point, normalize_basins
from normalizers.climate_outlook import normalize_outlook_feature
from normalizers.municipalities import normalize_municipality_feature
from normalizers.rainfall import normalize_rainfall
from normalizers.risk import build_assessment, infer_horizon, phase_for
from normalizers.soil import normalize_soil_features
from routes.canonical import _build_meta, _get_observations
from services import (
    open_meteo_forecast,
    snet_basins,
    snet_climate_outlook,
    snet_municipalities,
    snet_rainfall,
    snet_soil,
)
from utils.cache import DataCache
from utils.geo import find_nearest, haversine
from utils.time import EL_SALVADOR_TZ, now_utc_iso


_rain_cache = DataCache(ttl=Config.CACHE_TTL_RAINFALL)
_soil_cache = DataCache(ttl=Config.CACHE_TTL_SOIL)
_basin_cache = DataCache(ttl=Config.CACHE_TTL_BASINS)
_forecast_cache = DataCache(ttl=Config.CACHE_TTL_FORECAST_DAILY)
_outlook_cache = DataCache(ttl=Config.CACHE_TTL_CLIMATE_OUTLOOK)
_municipality_cache = DataCache(ttl=Config.CACHE_TTL_MUNICIPALITY_LOOKUP)

OUTLOOK_LAYER_BY_MONTH = {
    8: (12, "agosto"),
    9: (13, "septiembre"),
    10: (14, "octubre"),
    11: (15, "noviembre"),
}


def _distance_confidence(distance_km: float) -> str:
    if distance_km <= 10:
        return "alta"
    if distance_km <= 25:
        return "media"
    return "baja"


def _get_rainfall() -> tuple[list[dict], bool, str]:
    cached, stale = _rain_cache.get()
    if cached is not None and not stale:
        return cached, False, _rain_cache.fetched_at() or now_utc_iso()
    try:
        raw = snet_rainfall.fetch_all()
        rows = normalize_rainfall(raw)
        _rain_cache.set(rows)
        return rows, False, _rain_cache.fetched_at() or now_utc_iso()
    except Exception:
        if cached is not None:
            return cached, True, _rain_cache.fetched_at() or now_utc_iso()
        return [], False, now_utc_iso()


def _get_soils() -> tuple[list[dict], bool, str]:
    cached, stale = _soil_cache.get()
    if cached is not None and not stale:
        return cached, False, _soil_cache.fetched_at() or now_utc_iso()
    try:
        raw = snet_soil.fetch_all()
        rows = normalize_soil_features(raw)
        _soil_cache.set(rows)
        return rows, False, _soil_cache.fetched_at() or now_utc_iso()
    except Exception:
        if cached is not None:
            return cached, True, _soil_cache.fetched_at() or now_utc_iso()
        return [], False, now_utc_iso()


def _get_basins() -> tuple[list[dict], bool, str]:
    cached, stale = _basin_cache.get()
    if cached is not None and not stale:
        return cached, False, _basin_cache.fetched_at() or now_utc_iso()
    try:
        raw = snet_basins.fetch_all()
        rows = normalize_basins(raw)
        _basin_cache.set(rows)
        return rows, False, _basin_cache.fetched_at() or now_utc_iso()
    except Exception:
        if cached is not None:
            return cached, True, _basin_cache.fetched_at() or now_utc_iso()
        return [], False, now_utc_iso()


def _forecast_cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 4)}:{round(lon, 4)}"


def _get_forecast(lat: float, lon: float) -> tuple[dict | None, bool, str]:
    key = _forecast_cache_key(lat, lon)
    cached, stale = _forecast_cache.get(key)
    if cached is not None and not stale:
        return cached, False, _forecast_cache.fetched_at(key) or now_utc_iso()
    try:
        raw = open_meteo_forecast.fetch(lat, lon)
        _forecast_cache.set(raw, key)
        return raw, False, _forecast_cache.fetched_at(key) or now_utc_iso()
    except Exception:
        if cached is not None:
            return cached, True, _forecast_cache.fetched_at(key) or now_utc_iso()
        return None, False, now_utc_iso()


def _get_outlook(lat: float, lon: float, target_date: datetime.date) -> tuple[dict | None, bool, str, list[str]]:
    mapping = OUTLOOK_LAYER_BY_MONTH.get(target_date.month)
    if not mapping:
        return None, False, now_utc_iso(), [
            "No hay capa mensual validada para este mes en perspectivas_clima_servicio."
        ]

    layer_id, month_label = mapping
    key = f"{layer_id}:{round(lat, 4)}:{round(lon, 4)}"
    cached, stale = _outlook_cache.get(key)
    if cached is not None and not stale:
        return cached, False, _outlook_cache.fetched_at(key) or now_utc_iso(), []

    try:
        raw = snet_climate_outlook.fetch_point(layer_id, lat, lon)
        row = normalize_outlook_feature(raw, layer_id=layer_id, month_label=month_label, lat=lat, lon=lon)
        _outlook_cache.set(row, key)
        return row, False, _outlook_cache.fetched_at(key) or now_utc_iso(), []
    except Exception:
        if cached is not None:
            return cached, True, _outlook_cache.fetched_at(key) or now_utc_iso(), []
        return None, False, now_utc_iso(), [
            "No se pudo consultar perspectiva mensual puntual para esta ubicacion."
        ]


def _get_municipality(lat: float, lon: float) -> tuple[dict | None, bool, str]:
    key = f"{round(lat, 4)}:{round(lon, 4)}"
    cached, stale = _municipality_cache.get(key)
    if cached is not None and not stale:
        return cached, False, _municipality_cache.fetched_at(key) or now_utc_iso()
    try:
        raw = snet_municipalities.fetch_point(lat, lon)
        row = normalize_municipality_feature(raw, lat=lat, lon=lon)
        _municipality_cache.set(row, key)
        return row, False, _municipality_cache.fetched_at(key) or now_utc_iso()
    except Exception:
        if cached is not None:
            return cached, True, _municipality_cache.fetched_at(key) or now_utc_iso()
        return None, False, now_utc_iso()


def get_official_context(target_date: datetime.date) -> dict:
    valid_from = "2026-05-01"
    valid_until = "2026-08-31"
    canicula_watch = valid_from <= target_date.isoformat() <= valid_until
    return {
        "canicula_2026_watch": canicula_watch,
        "summary": (
            "Existe vigilancia oficial por canicula/periodos secos durante la epoca lluviosa 2026."
            if canicula_watch
            else "No hay una ventana oficial activa de vigilancia de canicula 2026 para esta fecha."
        ),
        "valid_from": valid_from,
        "valid_until": valid_until,
        "source_type": "escenario_estacional",
        "published_at": "2026-04-20",
        "snippets": [
            "Fuente oficial vigente para 2026 con vigilancia por canicula, periodos secos y temperaturas arriba de lo normal.",
            "Debe usarse como contexto estacional y no como lluvia puntual de parcela.",
        ],
        "sources_used": [
            "ambiente_canicula_2026",
        ],
    }


def get_phenology_context(crop: str, sowing_date: str, target_date: str | None = None) -> dict:
    reference_date = datetime.now(EL_SALVADOR_TZ).date()
    target = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else reference_date
    sowing = datetime.strptime(sowing_date, "%Y-%m-%d").date()
    days_after_sowing = (target - sowing).days
    phase_code, phase = phase_for(crop, days_after_sowing)

    max_susceptibility = max(
        phase["water"], phase["heat"], phase["evaporation"], phase["soil"], phase["seasonal"]
    )
    if max_susceptibility >= 1.0:
        susceptibility = "critica"
    elif max_susceptibility >= 0.8:
        susceptibility = "alta"
    elif max_susceptibility >= 0.5:
        susceptibility = "media"
    else:
        susceptibility = "baja"

    ui_phase_group = None
    if crop == "frijol" and 41 <= days_after_sowing <= 50:
        ui_phase_group = "Ventana reproductiva critica"

    return {
        "crop": crop,
        "days_after_sowing": days_after_sowing,
        "phase": phase["phase"],
        "phase_code": phase_code,
        "ui_phase_group": ui_phase_group,
        "susceptibility": susceptibility,
        "source": "sato_agro_phenology_table_v1",
        "note": (
            "Fase estimada; puede variar por variedad, altitud, temperatura, humedad y manejo."
        ),
    }


def get_weather_observed(lat: float, lon: float) -> tuple[dict, dict]:
    observations, obs_stale, obs_fetched_at = _get_observations()
    rainfall, rain_stale, rain_fetched_at = _get_rainfall()

    nearest_obs = find_nearest(lat, lon, observations) if observations else None
    nearest_rain = find_nearest(lat, lon, rainfall) if rainfall else None

    sources_used: list[str] = []
    warnings: list[str] = []

    rain_distance = None
    if nearest_rain:
        rain_distance = round(haversine(lat, lon, nearest_rain["lat"], nearest_rain["lon"]), 2)
        sources_used.append("snet_lluvia_data_24h")
    else:
        warnings.append("No se encontro estacion de lluvia cercana.")

    obs_distance = None
    if nearest_obs:
        obs_distance = round(haversine(lat, lon, nearest_obs["lat"], nearest_obs["lon"]), 2)
        sources_used.extend(["snet_temperatura_actual_max_min", "snet_viento_promedio_2horas"])
    else:
        warnings.append("No se encontro estacion meteorologica cercana.")

    data = {
        "source_type": "observado",
        "location": {"lat": lat, "lon": lon},
        "nearest_rain_station": {
            "station_id": nearest_rain["station_id"],
            "station_name": nearest_rain["station_name"],
            "distance_km": rain_distance,
            "confidence": _distance_confidence(rain_distance),
        } if nearest_rain and rain_distance is not None else None,
        "nearest_temperature_station": {
            "station_id": nearest_obs.get("station_id"),
            "station_name": nearest_obs.get("station_name"),
            "distance_km": obs_distance,
            "confidence": _distance_confidence(obs_distance),
        } if nearest_obs and obs_distance is not None else None,
        "nearest_wind_station": {
            "station_id": nearest_obs.get("station_id"),
            "station_name": nearest_obs.get("station_name"),
            "distance_km": obs_distance,
            "confidence": _distance_confidence(obs_distance),
        } if nearest_obs and obs_distance is not None else None,
        "rain_recent_mm": nearest_rain.get("rain_mm_period") if nearest_rain else None,
        "temperature_current_c": ((nearest_obs.get("temperature") or {}).get("current_c") if nearest_obs else None),
        "temperature_max_c": ((nearest_obs.get("temperature") or {}).get("max_c") if nearest_obs else None),
        "temperature_min_c": ((nearest_obs.get("temperature") or {}).get("min_c") if nearest_obs else None),
        "wind_speed_kmh": ((nearest_obs.get("wind") or {}).get("speed") if nearest_obs else None),
        "wind_direction_deg": ((nearest_obs.get("wind") or {}).get("direction_deg") if nearest_obs else None),
        "is_raining": nearest_rain.get("is_raining") if nearest_rain else None,
        "observed_at": nearest_obs.get("observed_at_local") if nearest_obs else None,
        "rain_observed_at": nearest_rain.get("obs_time_latest_local") if nearest_rain else None,
        "warnings": warnings,
        "sources_used": list(dict.fromkeys(sources_used)),
    }

    meta = _build_meta(
        cached=bool(nearest_obs or nearest_rain),
        stale=obs_stale or rain_stale,
        upstream_status="degraded" if (obs_stale or rain_stale) else "ok",
        fetched_at=max([ts for ts in (obs_fetched_at, rain_fetched_at) if ts], default=now_utc_iso()),
    )
    return data, meta


def get_weather_forecast(lat: float, lon: float, target_date: datetime.date | None = None) -> tuple[dict, dict]:
    target = target_date or datetime.now(EL_SALVADOR_TZ).date()
    raw, stale, fetched_at = _get_forecast(lat, lon)
    if not raw:
        return {
            "source_type": "pronosticado",
            "location": {"lat": lat, "lon": lon},
            "warnings": ["No se pudo obtener forecast Open-Meteo."],
            "sources_used": [],
        }, _build_meta(cached=False, stale=stale, upstream_status="failed", fetched_at=fetched_at)

    daily = raw.get("daily") or {}
    times = daily.get("time") or []
    target_in_range = target.isoformat() in times
    if target_in_range:
        idx = times.index(target.isoformat())
    else:
        idx = 0

    soil_moisture_model = None
    hourly = raw.get("hourly") or {}
    if hourly:
        surface = hourly.get("soil_moisture_0_to_1cm") or []
        mid = hourly.get("soil_moisture_1_to_3cm") or []
        deep = hourly.get("soil_moisture_3_to_9cm") or []
        values = [value for value in (surface + mid + deep) if value is not None]
        if values:
            avg = sum(values) / len(values)
            if avg < 0.15:
                soil_moisture_model = "baja"
            elif avg < 0.30:
                soil_moisture_model = "media"
            else:
                soil_moisture_model = "alta"

    data = {
        "source_type": "pronosticado",
        "location": {"lat": lat, "lon": lon},
        "target_date": times[idx] if times else target.isoformat(),
        "horizon": infer_horizon(datetime.now(EL_SALVADOR_TZ).date(), target),
        "rain_sum_mm": (daily.get("precipitation_sum") or [None])[idx] if target_in_range else None,
        "rain_probability_max": (daily.get("precipitation_probability_max") or [None])[idx] if target_in_range else None,
        "temp_max_c": (daily.get("temperature_2m_max") or [None])[idx] if target_in_range else None,
        "temp_min_c": (daily.get("temperature_2m_min") or [None])[idx] if target_in_range else None,
        "wind_max_kmh": (daily.get("wind_speed_10m_max") or [None])[idx] if target_in_range else None,
        "et0_sum_mm": (daily.get("et0_fao_evapotranspiration_sum") or [None])[idx] if target_in_range else None,
        "soil_moisture_model": soil_moisture_model,
        "sources_used": ["open_meteo_forecast"],
        "warnings": [] if target_in_range else [
            "Open-Meteo solo cubre 1-16 dias; para esta fecha el backend debe tratar el resultado como escenario."
        ],
    }
    meta = _build_meta(
        cached=True,
        stale=stale,
        upstream_status="degraded" if stale else "ok",
        fetched_at=fetched_at,
    )
    return data, meta


def get_geo_context(
    lat: float,
    lon: float,
    target_date: datetime.date,
    municipality: str | None = None,
    municipality_code: str | None = None,
    canton: str | None = None,
) -> tuple[dict, dict]:
    observed_weather, observed_meta = get_weather_observed(lat, lon)
    basins, basin_stale, basin_fetched_at = _get_basins()
    soils, soil_stale, soil_fetched_at = _get_soils()
    outlook, outlook_stale, outlook_fetched_at, outlook_warnings = _get_outlook(lat, lon, target_date)
    municipality_lookup, municipality_stale, municipality_fetched_at = _get_municipality(lat, lon)

    basin = basin_for_point(lat, lon, basins) if basins else None
    soil_context = None
    warnings = list(observed_weather.get("warnings") or [])
    warnings.extend(outlook_warnings)

    resolved_municipality = municipality or ((municipality_lookup or {}).get("municipality"))
    resolved_municipality_code = municipality_code or ((municipality_lookup or {}).get("municipality_code"))

    if resolved_municipality_code:
        soil_context = next((row for row in soils if row["municipality_code"] == resolved_municipality_code), None)
        if not soil_context:
            warnings.append("No se encontro contexto de suelo para municipality_code.")
    else:
        warnings.append("municipality_code no disponible; soil_context queda pendiente.")

    data = {
        "location": {"lat": lat, "lon": lon},
        "municipality": resolved_municipality,
        "municipality_code": resolved_municipality_code,
        "canton": canton,
        "basin_id": basin.get("basin_id") if basin else None,
        "nearest_rain_station": observed_weather.get("nearest_rain_station"),
        "nearest_temperature_station": observed_weather.get("nearest_temperature_station"),
        "nearest_wind_station": observed_weather.get("nearest_wind_station"),
        "soil_context": soil_context,
        "climate_outlook_context": outlook,
        "producer_vulnerability_context": None,
        "warnings": warnings,
        "sources_used": list(
            dict.fromkeys(
                (observed_weather.get("sources_used") or [])
                + (["snet_municipal_boundaries"] if municipality_lookup else [])
                + (["snet_datos_cuencas"] if basin else [])
                + (["snet_servicio_suelos_pais"] if soil_context else [])
                + (["snet_perspectivas_clima_servicio"] if outlook else [])
            )
        ),
    }
    meta = _build_meta(
        cached=True,
        stale=(
            observed_meta.get("stale", False)
            or municipality_stale
            or basin_stale
            or soil_stale
            or outlook_stale
        ),
        upstream_status="degraded"
        if (
            observed_meta.get("stale", False)
            or municipality_stale
            or basin_stale
            or soil_stale
            or outlook_stale
        )
        else "ok",
        fetched_at=max(
            [
                ts
                for ts in (
                    observed_meta.get("fetched_at"),
                    municipality_fetched_at,
                    basin_fetched_at,
                    soil_fetched_at,
                    outlook_fetched_at,
                )
                if ts
            ],
            default=now_utc_iso(),
        ),
    )
    return data, meta


def get_risk_assessment(arguments: dict) -> tuple[dict, dict, int]:
    crop = arguments.get("crop")
    sowing_date = arguments.get("sowing_date")
    lat = arguments.get("lat")
    lon = arguments.get("lon")
    if not crop or not sowing_date or lat is None or lon is None:
        return {"error": "crop, sowing_date, lat and lon are required"}, _build_meta(
            cached=False, stale=False, upstream_status="invalid_request", fetched_at=now_utc_iso()
        ), 400

    reference_date = datetime.now(EL_SALVADOR_TZ).date()
    target_date = datetime.strptime(arguments.get("target_date"), "%Y-%m-%d").date() if arguments.get("target_date") else reference_date
    horizon = infer_horizon(reference_date, target_date)

    observed, observed_meta = get_weather_observed(float(lat), float(lon))
    forecast, forecast_meta = get_weather_forecast(float(lat), float(lon), target_date)
    geo, geo_meta = get_geo_context(
        float(lat),
        float(lon),
        target_date,
        municipality=arguments.get("municipality"),
        municipality_code=arguments.get("municipality_code"),
        canton=arguments.get("canton"),
    )
    official = get_official_context(target_date)

    climate_payload = {
        "crop": crop,
        "sowing_date": sowing_date,
        "target_date": target_date.isoformat(),
        "lat": float(lat),
        "lon": float(lon),
        "soil": ((geo.get("soil_context") or {}).get("water_retention_modifier")),
        "seasonal": ((geo.get("climate_outlook_context") or {}).get("dryness_prior")),
        "canicula_watch": official["canicula_2026_watch"],
        "sources_used": list(
            dict.fromkeys(
                (observed.get("sources_used") or [])
                + (forecast.get("sources_used") or [])
                + (geo.get("sources_used") or [])
                + official["sources_used"]
            )
        ),
        "input_warnings": list(
            dict.fromkeys(
                (observed.get("warnings") or [])
                + (forecast.get("warnings") or [])
                + (geo.get("warnings") or [])
            )
        ),
    }

    if horizon == "present":
        climate_payload.update(
            {
                "rain_sum_mm": observed.get("rain_recent_mm"),
                "temp_max_c": observed.get("temperature_max_c") or observed.get("temperature_current_c"),
                "wind_max_kmh": observed.get("wind_speed_kmh"),
            }
        )
    elif horizon == "gt_16_days":
        climate_payload.update(
            {
                "temp_max_c": observed.get("temperature_max_c") or observed.get("temperature_current_c"),
                "wind_max_kmh": observed.get("wind_speed_kmh"),
            }
        )
        climate_payload["input_warnings"].append(
            "Para >16 dias el backend usa contexto estacional y fase de planta; no hay pronostico puntual Open-Meteo."
        )
    else:
        days_window = 3 if horizon == "1_3_days" else 7 if horizon == "4_7_days" else 16
        climate_payload.update(
            {
                "rain_sum_mm": forecast.get("rain_sum_mm"),
                "et0_sum_mm": forecast.get("et0_sum_mm"),
                "days_window": days_window,
                "temp_max_c": forecast.get("temp_max_c"),
                "wind_max_kmh": forecast.get("wind_max_kmh"),
                "et0_mm_day": (
                    round((forecast.get("et0_sum_mm") or 0.0) / days_window, 2)
                    if forecast.get("et0_sum_mm") is not None else None
                ),
            }
        )

    try:
        assessment = build_assessment(climate_payload, reference_date=reference_date)
    except ValueError as exc:
        return {"error": str(exc)}, _build_meta(
            cached=True,
            stale=False,
            upstream_status="invalid_request",
            fetched_at=max(
                [ts for ts in (observed_meta.get("fetched_at"), forecast_meta.get("fetched_at"), geo_meta.get("fetched_at")) if ts],
                default=now_utc_iso(),
            ),
        ), 400

    result = {
        **assessment.__dict__,
        "plant_state": assessment.plant_state.__dict__,
        "climate_state": assessment.climate_state.__dict__,
        "risk_factors": [item.__dict__ for item in assessment.risk_factors],
        "risk_overrides": [item.__dict__ for item in assessment.risk_overrides],
        "secondary_alerts": [item.__dict__ for item in assessment.secondary_alerts],
        "observed_weather": observed,
        "forecast_weather": forecast,
        "geo_context": geo,
        "official_context": official,
    }
    if assessment.plant_state.susceptibility:
        result["plant_state"]["susceptibility"] = assessment.plant_state.susceptibility.__dict__

    meta = _build_meta(
        cached=True,
        stale=observed_meta.get("stale", False) or forecast_meta.get("stale", False) or geo_meta.get("stale", False),
        upstream_status="degraded"
        if (observed_meta.get("stale", False) or forecast_meta.get("stale", False) or geo_meta.get("stale", False))
        else "ok",
        fetched_at=max(
            [ts for ts in (observed_meta.get("fetched_at"), forecast_meta.get("fetched_at"), geo_meta.get("fetched_at")) if ts],
            default=now_utc_iso(),
        ),
    )
    return result, meta, 200


def build_runtime_llm_context(arguments: dict) -> tuple[dict, dict, int]:
    crop = arguments.get("crop")
    sowing_date = arguments.get("sowing_date")
    lat = arguments.get("lat")
    lon = arguments.get("lon")
    target_date = arguments.get("target_date")
    if not crop or not sowing_date or lat is None or lon is None:
        return {"error": "crop, sowing_date, lat and lon are required"}, _build_meta(
            cached=False, stale=False, upstream_status="invalid_request", fetched_at=now_utc_iso()
        ), 400

    risk, meta, status = get_risk_assessment(arguments)
    if status != 200:
        return risk, meta, status

    selected_target_date = target_date or datetime.now(EL_SALVADOR_TZ).date().isoformat()
    current_datetime = datetime.now(EL_SALVADOR_TZ).isoformat()
    context = {
        "current_datetime": current_datetime,
        "timezone": "America/El_Salvador",
        "user_inputs": {
            "crop": crop,
            "sowing_date": sowing_date,
            "lat": float(lat),
            "lon": float(lon),
        },
        "ui_state": {
            "selected_target_date": selected_target_date,
            "selected_horizon": risk["horizon"],
            "visible_panel": arguments.get("visible_panel", "risk_summary"),
        },
        "plant_state": {
            **risk["plant_state"],
            "source": "sato_agro_phenology_table_v1",
        },
        "observed_weather": risk["observed_weather"],
        "forecast_weather": risk["forecast_weather"],
        "risk_assessment": {
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "confidence": risk["confidence"],
            "risk_factors": [
                {
                    "id": item["id"],
                    "label": item["label"],
                    "state": item["state"],
                    "contribution": item["contribution"],
                    "explanation": item["evidence"],
                }
                for item in risk["risk_factors"]
            ],
            "risk_overrides": risk["risk_overrides"],
            "secondary_alerts": risk["secondary_alerts"],
        },
        "recommendations": risk["recommendations"],
        "official_context": risk["official_context"],
        "source_policy": {
            "observed": "SNET/MARN observado local",
            "forecast": "Open-Meteo 1-16 dias",
            "scenario": ">16 dias o perspectiva mensual/canicula",
            "historical": "solo contexto, no alerta actual",
        },
    }
    return context, meta, 200


def explain_recommendation(payload: dict) -> dict:
    risk = payload.get("risk_assessment") or {}
    official = payload.get("official_context") or {}
    plant = payload.get("plant_state") or {}
    recommendations = payload.get("recommendations") or []

    phase = plant.get("phase") or "fase estimada"
    level = risk.get("risk_level") or "ATENCION"
    confidence = risk.get("confidence") or "media"
    factor_bits = []
    for factor in risk.get("risk_factors") or []:
        label = factor.get("label")
        state = factor.get("state")
        if label and state:
            factor_bits.append(f"{label.lower()} {state}")
    factor_text = ", ".join(factor_bits[:3]) if factor_bits else "senal climatica relevante"

    summary = (
        f"Tu cultivo esta en {phase}. El riesgo preventivo es {level} con confianza {confidence} "
        f"porque el backend detecta {factor_text}."
    )
    if official.get("canicula_2026_watch"):
        summary += " Ademas, existe vigilancia oficial por canicula o periodos secos en 2026."
    if recommendations:
        summary += " Acciones sugeridas: " + " ".join(recommendations[:3])

    return {
        "summary": summary,
        "audience": payload.get("audience", "productor"),
        "source_policy": {
            "observed": "SNET/MARN observado local",
            "forecast": "Open-Meteo 1-16 dias",
            "scenario": ">16 dias o perspectiva mensual/canicula",
            "historical": "solo contexto, no alerta actual",
        },
    }
