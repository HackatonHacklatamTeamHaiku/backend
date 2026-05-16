"""
Agro bulletin endpoint.

GET /api/v1/agro/latest — latest agro bulletin PDF metadata
"""

from __future__ import annotations

import logging

from datetime import datetime

from flask import Blueprint, jsonify, request

from config import Config
from normalizers.canonical import feature_row_from_observation, station_from_observation
from normalizers.rainfall import normalize_rainfall
from normalizers.risk import build_assessment
from services import snet_agro_pdf, snet_rainfall
from normalizers.agro import normalize_pdf
from models.schemas import to_dict
from routes.canonical import _build_meta, _get_observations
from utils.cache import DataCache
from utils.geo import find_nearest
from utils.time import EL_SALVADOR_TZ
from utils.time import now_utc_iso

logger = logging.getLogger(__name__)

bp = Blueprint("agro", __name__, url_prefix="/api/v1/agro")

_cache = DataCache(ttl=Config.CACHE_TTL_AGRO_PDF)
_cache_rain = DataCache(ttl=Config.CACHE_TTL_RAINFALL)


@bp.route("/latest")
def latest_agro():
    """Return the latest agro bulletin PDF metadata."""
    cached, stale = _cache.get()
    if cached is not None and not stale:
        return jsonify({
            "data": cached,
            "meta": {"cached": True, "stale": False, "upstream_status": "ok",
                     "fetched_at": _cache.fetched_at()},
        })

    try:
        raw = snet_agro_pdf.fetch()
        pdf_meta = normalize_pdf(raw, "agro_bulletin")
        data = to_dict(pdf_meta)
        _cache.set(data)
        return jsonify({
            "data": data,
            "meta": {"cached": False, "stale": False, "upstream_status": "ok",
                     "fetched_at": _cache.fetched_at()},
        })
    except Exception:
        logger.exception("Failed to fetch agro bulletin")
        if cached is not None:
            return jsonify({
                "data": cached,
                "meta": {"cached": True, "stale": True, "upstream_status": "failed",
                         "fetched_at": _cache.fetched_at()},
            })
        return jsonify({
            "data": None,
            "meta": {"cached": False, "stale": False, "upstream_status": "failed",
                     "fetched_at": now_utc_iso()},
        }), 502


def _get_rainfall() -> tuple[list[dict], bool, str]:
    cached, stale = _cache_rain.get()
    if cached is not None and not stale:
        return cached, False, _cache_rain.fetched_at() or now_utc_iso()

    try:
        raw = snet_rainfall.fetch_all()
        records = normalize_rainfall(raw)
        _cache_rain.set(records)
        return records, False, _cache_rain.fetched_at() or now_utc_iso()
    except Exception:
        logger.exception("Failed to fetch rainfall observations from SNET")
        if cached is not None:
            return cached, True, _cache_rain.fetched_at() or now_utc_iso()
        return [], False, now_utc_iso()


def _parse_bool(value: str | bool | None) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "si", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def build_advisory_payload(arguments: dict) -> tuple[dict, dict, int]:
    crop = arguments.get("crop")
    sowing_date = arguments.get("sowing_date")
    lat = arguments.get("lat")
    lon = arguments.get("lon")
    if not crop or not sowing_date or lat is None or lon is None:
        return {
            "error": "crop, sowing_date, lat and lon are required"
        }, {
            "cached": False,
            "stale": False,
            "upstream_status": "invalid_request",
            "fetched_at": now_utc_iso(),
        }, 400

    sources_used: list[str] = []
    assumptions: list[str] = []
    input_warnings: list[str] = []
    observed_meta = {
        "cached": False,
        "stale": False,
        "upstream_status": "ok",
        "fetched_at": now_utc_iso(),
    }

    temp_max_c = arguments.get("temp_max_c")
    wind_max_kmh = arguments.get("wind_max_kmh")
    nearest_station = None
    current_features = None
    reference_date = datetime.now(EL_SALVADOR_TZ).date()
    target_date_raw = arguments.get("target_date")
    is_present_horizon = True
    if target_date_raw:
        try:
            is_present_horizon = datetime.strptime(target_date_raw, "%Y-%m-%d").date() <= reference_date
        except ValueError:
            return {"error": "target_date must use YYYY-MM-DD"}, observed_meta, 400

    if temp_max_c is None or wind_max_kmh is None:
        observations, stale, fetched_at = _get_observations()
        observed_meta = _build_meta(
            cached=bool(observations),
            stale=stale,
            upstream_status="failed" if stale else "ok",
            fetched_at=fetched_at,
        )
        nearest_station = find_nearest(float(lat), float(lon), observations) if observations else None
        current_features = to_dict(feature_row_from_observation(nearest_station)) if nearest_station else None

        if current_features:
            sources_used.append("api_v1_features_current")
            if temp_max_c is None:
                feature_temp = current_features.get("temperature_max_c") or current_features.get("temperature_current_c")
                if feature_temp is not None:
                    temp_max_c = feature_temp
                    assumptions.append(
                        "temp_max_c se derivo desde la estacion SNET mas cercana usando temperatura maxima actual."
                    )
                else:
                    input_warnings.append(
                        "No se pudo derivar temp_max_c desde observaciones actuales; envie temp_max_c explicitamente."
                    )
            if wind_max_kmh is None:
                feature_wind = current_features.get("wind_speed")
                if feature_wind is not None:
                    wind_max_kmh = feature_wind
                    assumptions.append(
                        "wind_max_kmh se derivo desde la estacion SNET mas cercana usando velocidad de viento actual."
                    )
                else:
                    input_warnings.append(
                        "No se pudo derivar wind_max_kmh desde observaciones actuales; envie wind_max_kmh explicitamente."
                    )
        else:
            input_warnings.append(
                "No se encontro estacion cercana para derivar temperatura/viento; envie temp_max_c y wind_max_kmh."
            )

    rain_sum_mm = arguments.get("rain_sum_mm")
    if rain_sum_mm is None:
        if is_present_horizon:
            rainfall_rows, rain_stale, rain_fetched_at = _get_rainfall()
            rain_meta = _build_meta(
                cached=bool(rainfall_rows),
                stale=rain_stale,
                upstream_status="failed" if rain_stale else "ok",
                fetched_at=rain_fetched_at,
            )
            observed_meta = {
                "cached": observed_meta.get("cached", False) or rain_meta.get("cached", False),
                "stale": observed_meta.get("stale", False) or rain_meta.get("stale", False),
                "upstream_status": "degraded" if (
                    observed_meta.get("stale", False) or rain_meta.get("stale", False)
                ) else observed_meta.get("upstream_status", "ok"),
                "fetched_at": max(
                    [ts for ts in (observed_meta.get("fetched_at"), rain_meta.get("fetched_at")) if ts],
                    default=now_utc_iso(),
                ),
            }
            nearest_rain = find_nearest(float(lat), float(lon), rainfall_rows) if rainfall_rows else None
            if nearest_rain:
                rain_sum_mm = nearest_rain.get("rain_mm_period")
                sources_used.append("snet_lluvia_data_24h")
                assumptions.append(
                    "rain_sum_mm se derivo desde la estacion de lluvia 24h mas cercana usando valor_acumulado."
                )
            else:
                input_warnings.append(
                    "No se pudo derivar rain_sum_mm desde lluvia 24h; envie rain_sum_mm explicitamente."
                )
        else:
            input_warnings.append(
                "lluvia_data_24h solo cubre observado reciente; para horizontes futuros envie rain_sum_mm pronosticado."
            )

    try:
        canicula_watch = _parse_bool(arguments.get("canicula_watch"))
    except ValueError as exc:
        return {"error": str(exc)}, observed_meta, 400

    payload = {
        "crop": crop,
        "sowing_date": sowing_date,
        "target_date": target_date_raw,
        "lat": float(lat),
        "lon": float(lon),
        "rain_sum_mm": rain_sum_mm,
        "et0_sum_mm": arguments.get("et0_sum_mm"),
        "days_window": arguments.get("days_window"),
        "dry_days": arguments.get("dry_days"),
        "temp_max_c": temp_max_c,
        "wind_max_kmh": wind_max_kmh,
        "et0_mm_day": arguments.get("et0_mm_day"),
        "soil": arguments.get("soil"),
        "seasonal": arguments.get("seasonal"),
        "canicula_watch": canicula_watch,
        "sources_used": sources_used + (["manual_query_inputs"] if any(
            arguments.get(key) is not None for key in (
                "rain_sum_mm", "et0_sum_mm", "days_window", "dry_days",
                "temp_max_c", "wind_max_kmh", "et0_mm_day", "soil",
                "seasonal", "canicula_watch",
            )
        ) else []),
        "assumptions": assumptions,
        "input_warnings": input_warnings,
    }

    try:
        assessment = build_assessment(payload, reference_date=reference_date)
    except ValueError as exc:
        return {"error": str(exc)}, observed_meta, 400

    response = to_dict(assessment)
    if current_features:
        response["station"] = to_dict(station_from_observation(nearest_station))
        response["features"] = current_features
    return response, observed_meta, 200


@bp.route("/advisory")
def agro_advisory():
    """Return a transparent MVP agroclimatic advisory assessment."""
    data, meta, status = build_advisory_payload(request.args.to_dict())
    return jsonify({"data": data, "meta": meta}), status
