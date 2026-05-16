"""
Build canonical frontend + ML-friendly records from normalized backend data.
"""

from __future__ import annotations

from models.schemas import (
    DocumentRecord,
    ObservationFeatureRow,
    Station,
)
from utils.time import age_minutes_from_iso


def station_from_observation(observation: dict) -> Station:
    """Build a canonical station record from an observation payload."""
    return Station(
        station_id=observation.get("station_id", 0),
        station_code=observation.get("station_code", ""),
        station_name=observation.get("station_name", ""),
        station_label=observation.get("station_label", ""),
        source=observation.get("source", "snet"),
        lat=observation.get("lat", 0.0),
        lon=observation.get("lon", 0.0),
    )


def feature_row_from_observation(observation: dict) -> ObservationFeatureRow:
    """Flatten nested observation JSON into one ML-friendly feature row."""
    temperature = observation.get("temperature") or {}
    wind = observation.get("wind") or {}

    current_c = temperature.get("current_c")
    max_c = temperature.get("max_c")
    min_c = temperature.get("min_c")
    diurnal_range = None
    if max_c is not None and min_c is not None:
        diurnal_range = round(max_c - min_c, 2)

    wind_direction = wind.get("direction_deg")
    wind_speed = wind.get("speed")

    has_temperature = any(
        value is not None for value in (current_c, max_c, min_c)
    )
    has_wind = any(
        value is not None for value in (wind_direction, wind_speed)
    )

    return ObservationFeatureRow(
        station_id=observation.get("station_id", 0),
        station_code=observation.get("station_code", ""),
        station_name=observation.get("station_name", ""),
        station_label=observation.get("station_label", ""),
        source=observation.get("source", "snet"),
        lat=observation.get("lat", 0.0),
        lon=observation.get("lon", 0.0),
        observed_at=observation.get("observed_at"),
        observed_at_local=observation.get("observed_at_local"),
        observation_age_minutes=age_minutes_from_iso(observation.get("observed_at")),
        temperature_current_c=current_c,
        temperature_max_c=max_c,
        temperature_min_c=min_c,
        temperature_diurnal_range_c=diurnal_range,
        wind_direction_deg=wind_direction,
        wind_speed=wind_speed,
        has_temperature=has_temperature,
        has_wind=has_wind,
        is_complete=has_temperature and has_wind,
    )


def forecast_document_from_payload(forecast: dict, source_url: str) -> DocumentRecord:
    """Convert the 48-hour forecast payload into a retrievable document record."""
    periods = forecast.get("periods") or {}
    content_parts = [
        forecast.get("headline"),
        periods.get("morning"),
        periods.get("afternoon"),
        periods.get("night"),
    ]
    content_text = "\n".join(part for part in content_parts if part) or None

    return DocumentRecord(
        document_id="snet-forecast-48h",
        document_type="forecast_48h",
        title="SNET 48-hour forecast",
        summary=forecast.get("headline"),
        source=forecast.get("source", "snet"),
        url=source_url,
        issued_at=forecast.get("issued_for"),
        content_text=content_text,
    )


def pdf_document_from_payload(
    payload: dict,
    *,
    document_id: str,
    document_type: str,
    default_title: str,
    default_summary: str,
) -> DocumentRecord:
    """Convert PDF metadata into a canonical document record."""
    return DocumentRecord(
        document_id=document_id,
        document_type=document_type,
        title=payload.get("title") or default_title,
        summary=default_summary,
        source=payload.get("source", "snet"),
        url=payload.get("url"),
        last_modified=payload.get("last_modified"),
    )
