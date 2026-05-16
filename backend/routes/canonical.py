"""
Canonical document route plus shared helpers for AI tools and backend composition.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from config import Config
from models.schemas import to_dict
from normalizers.agro import normalize_pdf
from normalizers.canonical import forecast_document_from_payload, pdf_document_from_payload
from normalizers.forecasts import normalize_48h
from normalizers.observations import extract_station_ids, merge_observations
from services import (
    snet_agro_pdf,
    snet_forecast_48h,
    snet_station_metadata,
    snet_temperature,
    snet_weekly_pdf,
    snet_wind,
)
from utils.cache import DataCache
from utils.time import now_utc_iso

logger = logging.getLogger(__name__)

bp = Blueprint("canonical", __name__, url_prefix="/api/v1")

_cache_obs = DataCache(ttl=Config.CACHE_TTL_OBSERVATIONS)
_cache_48h = DataCache(ttl=Config.CACHE_TTL_FORECAST_48H)
_cache_weekly = DataCache(ttl=Config.CACHE_TTL_WEEKLY_PDF)
_cache_agro = DataCache(ttl=Config.CACHE_TTL_AGRO_PDF)


def _build_meta(*, cached: bool, stale: bool, upstream_status: str, fetched_at: str | None):
    return {
        "cached": cached,
        "stale": stale,
        "upstream_status": upstream_status,
        "fetched_at": fetched_at or now_utc_iso(),
    }


def _get_observations() -> tuple[list[dict], bool, str]:
    cached, stale = _cache_obs.get()
    if cached is not None and not stale:
        return cached, False, _cache_obs.fetched_at() or now_utc_iso()

    try:
        temp_raw = snet_temperature.fetch_all()
        wind_raw = snet_wind.fetch_all()
        station_metadata = snet_station_metadata.get_many(
            extract_station_ids(temp_raw, wind_raw)
        )
        observations = merge_observations(
            temp_raw,
            wind_raw,
            station_metadata=station_metadata,
        )
        data = [to_dict(obs) for obs in observations]
        _cache_obs.set(data)
        return data, False, _cache_obs.fetched_at() or now_utc_iso()
    except Exception:
        logger.exception("Canonical routes: failed to fetch observations")
        if cached is not None:
            return cached, True, _cache_obs.fetched_at() or now_utc_iso()
        return [], False, now_utc_iso()


def _get_forecast_document() -> tuple[dict | None, bool, str]:
    cached, stale = _cache_48h.get()
    if cached is not None and not stale:
        return cached, False, _cache_48h.fetched_at() or now_utc_iso()

    try:
        html = snet_forecast_48h.fetch()
        forecast = normalize_48h(html)
        forecast_data = to_dict(forecast)
        document = to_dict(
            forecast_document_from_payload(
                forecast_data,
                Config.SNET_FORECAST_48H_URL,
            )
        )
        _cache_48h.set(document)
        return document, False, _cache_48h.fetched_at() or now_utc_iso()
    except Exception:
        logger.exception("Canonical routes: failed to fetch 48h forecast document")
        if cached is not None:
            return cached, True, _cache_48h.fetched_at() or now_utc_iso()
        return None, False, now_utc_iso()


def _get_weekly_document() -> tuple[dict | None, bool, str]:
    cached, stale = _cache_weekly.get()
    if cached is not None and not stale:
        return cached, False, _cache_weekly.fetched_at() or now_utc_iso()

    try:
        raw = snet_weekly_pdf.fetch()
        pdf_meta = normalize_pdf(raw, "weekly_forecast")
        payload = to_dict(pdf_meta)
        document = to_dict(
            pdf_document_from_payload(
                payload,
                document_id="snet-weekly-forecast-pdf",
                document_type="weekly_forecast_pdf",
                default_title="SNET weekly forecast PDF",
                default_summary="Latest weekly forecast PDF published by SNET.",
            )
        )
        _cache_weekly.set(document)
        return document, False, _cache_weekly.fetched_at() or now_utc_iso()
    except Exception:
        logger.exception("Canonical routes: failed to fetch weekly document")
        if cached is not None:
            return cached, True, _cache_weekly.fetched_at() or now_utc_iso()
        return None, False, now_utc_iso()


def _get_agro_document() -> tuple[dict | None, bool, str]:
    cached, stale = _cache_agro.get()
    if cached is not None and not stale:
        return cached, False, _cache_agro.fetched_at() or now_utc_iso()

    try:
        raw = snet_agro_pdf.fetch()
        pdf_meta = normalize_pdf(raw, "agro_bulletin")
        payload = to_dict(pdf_meta)
        document = to_dict(
            pdf_document_from_payload(
                payload,
                document_id="snet-agro-bulletin-pdf",
                document_type="agro_bulletin_pdf",
                default_title="SNET agrometeorological bulletin PDF",
                default_summary="Latest agrometeorological bulletin published by SNET.",
            )
        )
        _cache_agro.set(document)
        return document, False, _cache_agro.fetched_at() or now_utc_iso()
    except Exception:
        logger.exception("Canonical routes: failed to fetch agro document")
        if cached is not None:
            return cached, True, _cache_agro.fetched_at() or now_utc_iso()
        return None, False, now_utc_iso()


@bp.route("/documents/latest")
def latest_documents():
    """Return canonical latest forecast and bulletin document records."""
    forecast_doc, forecast_stale, forecast_fetched_at = _get_forecast_document()
    weekly_doc, weekly_stale, weekly_fetched_at = _get_weekly_document()
    agro_doc, agro_stale, agro_fetched_at = _get_agro_document()

    documents = [
        doc for doc in (forecast_doc, weekly_doc, agro_doc)
        if doc is not None
    ]
    any_stale = forecast_stale or weekly_stale or agro_stale
    latest_fetched_at = max(
        [ts for ts in (forecast_fetched_at, weekly_fetched_at, agro_fetched_at) if ts],
        default=now_utc_iso(),
    )

    return jsonify({
        "data": documents,
        "meta": _build_meta(
            cached=bool(documents),
            stale=any_stale,
            upstream_status="degraded" if any_stale else "ok",
            fetched_at=latest_fetched_at,
        ),
    })
