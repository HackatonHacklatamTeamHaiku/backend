"""
Composition helpers that align backend responses with the manifest contract.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta

from config import Config
from normalizers.basins import basin_for_point, normalize_basins
from normalizers.climate_outlook import normalize_outlook_feature
from normalizers.municipalities import normalize_municipality_feature
from normalizers.rainfall import normalize_rainfall
from normalizers.risk import build_assessment, default_days_window, infer_horizon, phase_for
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

EL_SALVADOR_BOUNDS = {
    "lat_min": 13.0,
    "lat_max": 14.6,
    "lon_min": -90.3,
    "lon_max": -87.6,
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COORDINATE_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")

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


def _parse_request_date(value: str, field_name: str) -> date:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a valid date in YYYY-MM-DD format")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid date in YYYY-MM-DD format")


def _parse_coordinate(value: str, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite decimal number")
    if isinstance(value, (int, float)):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"{field_name} must be a finite decimal number")
        return parsed
    if not isinstance(value, str) or not COORDINATE_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a finite decimal number")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a finite decimal number")
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} must be a finite decimal number")
    return parsed


def _validate_supported_location(lat: float, lon: float) -> None:
    if not (
        EL_SALVADOR_BOUNDS["lat_min"] <= lat <= EL_SALVADOR_BOUNDS["lat_max"]
        and EL_SALVADOR_BOUNDS["lon_min"] <= lon <= EL_SALVADOR_BOUNDS["lon_max"]
    ):
        raise ValueError("lat and lon must be within the supported El Salvador region")


def _data_quality_confidence(assumptions: list[str], warnings: list[str]) -> tuple[str, list[str]]:
    reasons = ["horizon_confidence reflects forecast horizon only."]
    if assumptions:
        reasons.append("Some model inputs used explicit assumptions.")
    if warnings:
        reasons.append("Some source or context warnings were present.")
    if assumptions:
        return "media_baja", reasons
    if warnings:
        return "media", reasons
    return "alta", reasons


def _risk_window_weather_from_payload(payload: dict) -> dict:
    if payload.get("scenario_mode") == "seasonal":
        return {
            "source_type": "escenario",
            "window": None,
            "rain_sum_mm": None,
            "et0_sum_mm": None,
            "days_window": payload.get("days_window"),
            "dry_days": None,
            "temp_max_c": None,
            "wind_max_kmh": None,
            "et0_mm_day": None,
            "note": "Escenario estacional sin pronostico puntual diario.",
        }
    return {
        "source_type": "forecast_window" if payload.get("forecast_window") else "observado_modelado",
        "window": payload.get("forecast_window") or {
            "start": payload.get("target_date"),
            "end": payload.get("target_date"),
            "days": payload.get("days_window"),
        },
        "rain_sum_mm": payload.get("rain_sum_mm"),
        "et0_sum_mm": payload.get("et0_sum_mm"),
        "days_window": payload.get("days_window"),
        "dry_days": payload.get("dry_days"),
        "temp_max_c": payload.get("temp_max_c"),
        "wind_max_kmh": payload.get("wind_max_kmh"),
        "et0_mm_day": payload.get("et0_mm_day"),
    }


def _source_roles(climate_payload: dict, observed: dict, forecast: dict, geo: dict, official: dict) -> dict:
    context_sources = list(
        dict.fromkeys(
            (observed.get("sources_used") or [])
            + (forecast.get("sources_used") or [])
            + (geo.get("sources_used") or [])
            + (official.get("sources_used") or [])
        )
    )
    model_default_inputs = []
    if climate_payload.get("soil") is None:
        model_default_inputs.append("soil=neutral")
    if climate_payload.get("seasonal") is None:
        model_default_inputs.append("seasonal=normal")

    if climate_payload.get("scenario_mode") == "seasonal":
        scoring_sources = list(
            dict.fromkeys(
                [source for source in (geo.get("sources_used") or []) if source in {"snet_servicio_suelos_pais", "snet_perspectivas_clima_servicio"}]
                + (official.get("sources_used") or [])
                + ["sato_agro_phenology_table_v1"]
            )
        )
    else:
        weather_sources = (forecast.get("sources_used") or ["open_meteo_forecast"]) if climate_payload.get("forecast_window") else (
            (observed.get("sources_used") or []) + ["open_meteo_forecast"]
        )
        scoring_sources = list(
            dict.fromkeys(
                weather_sources
                + [source for source in (geo.get("sources_used") or []) if source in {"snet_servicio_suelos_pais", "snet_perspectivas_clima_servicio"}]
                + (official.get("sources_used") or [])
                + ["sato_agro_phenology_table_v1"]
            )
        )
    return {"scoring_sources": scoring_sources, "context_sources": context_sources, "model_default_inputs": model_default_inputs}


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


def _forecast_dates(raw: dict) -> list[date]:
    times = ((raw.get("daily") or {}).get("time") or []) if raw else []
    return [datetime.strptime(item, "%Y-%m-%d").date() for item in times]


def _daily_series(raw: dict, key: str) -> list:
    return (raw.get("daily") or {}).get(key) or []


def _forecast_window_summary(raw: dict, reference_date: date, target_date: date) -> dict:
    forecast_dates = _forecast_dates(raw)
    if not forecast_dates:
        raise ValueError("Open-Meteo forecast daily series is empty")
    if target_date not in forecast_dates:
        raise ValueError("target_date is outside Open-Meteo forecast range")

    start_date = reference_date if target_date <= reference_date else reference_date + timedelta(days=1)
    selected_indexes = [
        idx
        for idx, item_date in enumerate(forecast_dates)
        if start_date <= item_date <= target_date
    ]
    if not selected_indexes:
        raise ValueError("target_date is outside Open-Meteo forecast range")

    precipitation = _daily_series(raw, "precipitation_sum")
    et0 = _daily_series(raw, "et0_fao_evapotranspiration_sum")
    temp_max = _daily_series(raw, "temperature_2m_max")
    wind_max = _daily_series(raw, "wind_speed_10m_max")

    def values(series: list) -> list[float]:
        return [float(series[idx]) for idx in selected_indexes if idx < len(series) and series[idx] is not None]

    rain_values = values(precipitation)
    et0_values = values(et0)
    temp_values = values(temp_max)
    wind_values = values(wind_max)
    if not rain_values or not et0_values or not temp_values or not wind_values:
        raise ValueError("Open-Meteo forecast missing required daily values for risk window")

    days_window = len(selected_indexes)
    et0_sum_mm = round(sum(et0_values), 4)
    return {
        "rain_sum_mm": round(sum(rain_values), 4),
        "et0_sum_mm": et0_sum_mm,
        "days_window": days_window,
        "dry_days": sum(1 for value in rain_values if value < 1.0),
        "temp_max_c": max(temp_values),
        "wind_max_kmh": max(wind_values),
        "et0_mm_day": round(et0_sum_mm / max(days_window, 1), 4),
        "derived_inputs": [
            (
                f"Forecast agregado desde {forecast_dates[selected_indexes[0]].isoformat()} "
                f"hasta {forecast_dates[selected_indexes[-1]].isoformat()}."
            ),
            "dry_days calculado desde precipitation_sum < 1 mm.",
            "et0_mm_day derivado como et0_sum_mm / days_window.",
        ],
        "forecast_window": {
            "start": forecast_dates[selected_indexes[0]].isoformat(),
            "end": forecast_dates[selected_indexes[-1]].isoformat(),
            "days": days_window,
        },
    }


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
    if days_after_sowing < 0:
        raise ValueError("target_date cannot be earlier than sowing_date")
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
        "source_type": "pronosticado" if target_in_range else "escenario",
        "location": {"lat": lat, "lon": lon},
        "target_date": target.isoformat(),
        "target_in_forecast_range": target_in_range,
        "horizon": infer_horizon(datetime.now(EL_SALVADOR_TZ).date(), target),
        "rain_sum_mm": (daily.get("precipitation_sum") or [None])[idx] if target_in_range else None,
        "rain_probability_max": (daily.get("precipitation_probability_max") or [None])[idx] if target_in_range else None,
        "temp_max_c": (daily.get("temperature_2m_max") or [None])[idx] if target_in_range else None,
        "temp_min_c": (daily.get("temperature_2m_min") or [None])[idx] if target_in_range else None,
        "wind_max_kmh": (daily.get("wind_speed_10m_max") or [None])[idx] if target_in_range else None,
        "et0_sum_mm": (daily.get("et0_fao_evapotranspiration_sum") or [None])[idx] if target_in_range else None,
        "soil_moisture_model": soil_moisture_model if target_in_range else None,
        "soil_moisture_model_scope": "available_forecast_hourly_window" if target_in_range and soil_moisture_model else None,
        "sources_used": ["open_meteo_forecast"] if target_in_range else [],
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
    try:
        parsed_lat = _parse_coordinate(lat, "lat")
        parsed_lon = _parse_coordinate(lon, "lon")
        _validate_supported_location(parsed_lat, parsed_lon)
        parsed_sowing_date = _parse_request_date(sowing_date, "sowing_date")
        target_date = _parse_request_date(arguments.get("target_date"), "target_date") if arguments.get("target_date") else reference_date
    except ValueError as exc:
        return {"error": str(exc)}, _build_meta(
            cached=False, stale=False, upstream_status="invalid_request", fetched_at=now_utc_iso()
        ), 400

    if target_date < reference_date:
        return {"error": "target_date cannot be earlier than today for risk assessment"}, _build_meta(
            cached=False, stale=False, upstream_status="invalid_request", fetched_at=now_utc_iso()
        ), 400

    if target_date < parsed_sowing_date:
        return {"error": "target_date cannot be earlier than sowing_date"}, _build_meta(
            cached=False, stale=False, upstream_status="invalid_request", fetched_at=now_utc_iso()
        ), 400

    horizon = infer_horizon(reference_date, target_date)

    observed, observed_meta = get_weather_observed(parsed_lat, parsed_lon)
    forecast, forecast_meta = get_weather_forecast(parsed_lat, parsed_lon, target_date)
    raw_forecast, _, _ = _get_forecast(parsed_lat, parsed_lon)
    geo, geo_meta = get_geo_context(
        parsed_lat,
        parsed_lon,
        target_date,
        municipality=arguments.get("municipality"),
        municipality_code=arguments.get("municipality_code"),
        canton=arguments.get("canton"),
    )
    official = get_official_context(target_date)

    climate_payload = {
        "crop": crop,
        "sowing_date": parsed_sowing_date.isoformat(),
        "target_date": target_date.isoformat(),
        "lat": parsed_lat,
        "lon": parsed_lon,
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
        derived_inputs = []
        et0_sum_mm = None
        et0_mm_day = None
        if raw_forecast:
            try:
                today_summary = _forecast_window_summary(raw_forecast, reference_date, reference_date)
                et0_sum_mm = today_summary["et0_sum_mm"]
                et0_mm_day = today_summary["et0_mm_day"]
                derived_inputs.append("ET0 de hoy tomado de Open-Meteo como demanda atmosferica modelada.")
            except ValueError as exc:
                climate_payload["input_warnings"].append(str(exc))

        rain_sum_mm = observed.get("rain_recent_mm")
        dry_days = None
        if rain_sum_mm is not None:
            dry_days = 1 if float(rain_sum_mm) < 1.0 else 0
            derived_inputs.append("dry_days calculado desde lluvia observada 24h < 1 mm.")

        climate_payload.update(
            {
                "rain_sum_mm": rain_sum_mm,
                "et0_sum_mm": et0_sum_mm,
                "days_window": 1,
                "dry_days": dry_days,
                "temp_max_c": observed.get("temperature_max_c") or observed.get("temperature_current_c"),
                "wind_max_kmh": observed.get("wind_speed_kmh"),
                "et0_mm_day": et0_mm_day,
                "derived_inputs": derived_inputs,
            }
        )
    elif horizon == "gt_16_days":
        climate_payload.update(
            {
                "scenario_mode": "seasonal",
                "days_window": 20,
                "derived_inputs": [
                    "Escenario estacional calculado sin pronostico puntual de lluvia diaria."
                ],
            }
        )
        climate_payload["input_warnings"].append(
            "Para esta fecha el backend usa contexto estacional y fase de planta; no hay pronostico puntual Open-Meteo completo."
        )
    else:
        if raw_forecast:
            try:
                climate_payload.update(_forecast_window_summary(raw_forecast, reference_date, target_date))
            except ValueError as exc:
                climate_payload["input_warnings"].append(str(exc))
                climate_payload.update(
                    {
                        "scenario_mode": "seasonal",
                        "days_window": default_days_window(horizon),
                        "derived_inputs": [
                            "Escenario estacional usado porque el target no tiene pronostico diario Open-Meteo completo."
                        ],
                    }
                )
        else:
            climate_payload["input_warnings"].append("No se pudo obtener forecast Open-Meteo para la ventana de riesgo.")
            climate_payload.update(
                {
                    "scenario_mode": "seasonal",
                    "days_window": default_days_window(horizon),
                    "derived_inputs": [
                        "Escenario estacional usado porque no hubo forecast Open-Meteo disponible."
                    ],
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

    data_quality_confidence, confidence_reasons = _data_quality_confidence(
        assessment.assumptions,
        assessment.input_warnings,
    )

    result = {
        **assessment.__dict__,
        "horizon_confidence": assessment.confidence,
        "data_quality_confidence": data_quality_confidence,
        "confidence_reasons": confidence_reasons,
        "plant_state": assessment.plant_state.__dict__,
        "climate_state": assessment.climate_state.__dict__,
        "risk_factors": [item.__dict__ for item in assessment.risk_factors],
        "risk_overrides": [item.__dict__ for item in assessment.risk_overrides],
        "secondary_alerts": [item.__dict__ for item in assessment.secondary_alerts],
        "risk_window_weather": _risk_window_weather_from_payload(climate_payload),
        "source_roles": _source_roles(climate_payload, observed, forecast, geo, official),
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

    missing_required_user_data = []
    if not crop:
        missing_required_user_data.append("crop")
    if not sowing_date:
        missing_required_user_data.append("sowing_date")
    if lat is None:
        missing_required_user_data.append("lat")
    if lon is None:
        missing_required_user_data.append("lon")

    if missing_required_user_data:
        return {
            "error": "crop, sowing_date, lat and lon are required",
            "missing_required_user_data": missing_required_user_data,
        }, _build_meta(
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
        "missing_required_user_data": [],
        "plant_state": {
            **risk["plant_state"],
            "source": "sato_agro_phenology_table_v1",
        },
        "observed_weather": risk["observed_weather"],
        "forecast_weather": risk["forecast_weather"],
        "risk_window_weather": risk.get("risk_window_weather"),
        "risk_assessment": {
            "target_date": risk["target_date"],
            "horizon": risk["horizon"],
            "risk_score": risk["risk_score"],
            "risk_level_base": risk.get("risk_level_base"),
            "risk_level": risk["risk_level"],
            "confidence": risk["confidence"],
            "horizon_confidence": risk.get("horizon_confidence"),
            "data_quality_confidence": risk.get("data_quality_confidence"),
            "confidence_reasons": risk.get("confidence_reasons"),
            "climate_state": risk.get("climate_state"),
            "risk_factors": [
                {
                    "id": item["id"],
                    "label": item["label"],
                    "state": item["state"],
                    "climate_value": item.get("climate_value"),
                    "plant_susceptibility": item.get("plant_susceptibility"),
                    "contribution": item["contribution"],
                    "explanation": item["evidence"],
                }
                for item in risk["risk_factors"]
            ],
            "risk_overrides": risk["risk_overrides"],
            "secondary_alerts": risk["secondary_alerts"],
            "sources_used": risk.get("sources_used"),
            "source_roles": risk.get("source_roles"),
            "derived_inputs": risk.get("derived_inputs"),
            "assumptions": risk.get("assumptions"),
            "input_warnings": risk.get("input_warnings"),
        },
        "recommendations": risk["recommendations"],
        "official_context": risk["official_context"],
        "sources_used": risk["sources_used"],
        "source_policy": {
            "observed": "SNET/MARN observado local",
            "forecast": "Open-Meteo 1-16 dias",
            "scenario": ">16 dias o perspectiva mensual/canicula",
            "historical": "solo contexto, no alerta actual",
        },
    }
    return context, meta, 200


def explain_recommendation(payload: dict) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    risk = payload.get("risk_assessment") if isinstance(payload.get("risk_assessment"), dict) else {}
    official = payload.get("official_context") if isinstance(payload.get("official_context"), dict) else {}
    plant = payload.get("plant_state") if isinstance(payload.get("plant_state"), dict) else {}
    recommendations = payload.get("recommendations") if isinstance(payload.get("recommendations"), list) else []

    phase = plant.get("phase") or "fase estimada"
    level = risk.get("risk_level") or "ATENCION"
    horizon_confidence = risk.get("horizon_confidence") or risk.get("confidence") or "media"
    data_quality_confidence = risk.get("data_quality_confidence")
    factor_bits = []
    for factor in (risk.get("risk_factors") if isinstance(risk.get("risk_factors"), list) else []):
        if not isinstance(factor, dict):
            continue
        label = factor.get("label")
        state = factor.get("state")
        if label and state:
            factor_bits.append(f"{label.lower()} {state}")
    factor_text = ", ".join(factor_bits[:3]) if factor_bits else "senal climatica relevante"

    confidence_text = f"confianza de horizonte {horizon_confidence}"
    if data_quality_confidence and data_quality_confidence != horizon_confidence:
        confidence_text += f" y calidad de datos {data_quality_confidence}"

    summary = (
        f"Tu cultivo esta en {phase}. El riesgo preventivo es {level} con {confidence_text} "
        f"porque el backend detecta {factor_text}."
    )
    if risk.get("assumptions") or risk.get("input_warnings"):
        summary += " La evaluacion incluye supuestos o advertencias de datos que deben revisarse."
    climate_state = risk.get("climate_state") or {}
    if risk.get("horizon") == "gt_16_days" or climate_state.get("rain") == "escenario estacional":
        summary += " Esta evaluacion es un escenario estacional, no un pronostico puntual de lluvia en parcela."
    if official.get("canicula_2026_watch"):
        summary += " Ademas, existe vigilancia oficial por canicula o periodos secos en 2026."
    secondary_alerts = risk.get("secondary_alerts") if isinstance(risk.get("secondary_alerts"), list) else []
    if secondary_alerts:
        first_alert = secondary_alerts[0] if isinstance(secondary_alerts[0], dict) else {}
        alert_text = first_alert.get("message") or "hay una alerta secundaria relevante."
        summary += f" Alerta secundaria: {alert_text}"
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
