"""
Data schemas — the single source of truth for every JSON shape
the API can return.

Uses dataclasses + a to_dict() helper instead of Pydantic
(pydantic-core doesn't compile on Python 3.14 yet).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


def to_dict(obj) -> dict:
    """Recursively convert a dataclass instance to a plain dict."""
    return asdict(obj)


# ── Observation ──────────────────────────────────────────────

@dataclass
class Temperature:
    current_c: Optional[float] = None
    max_c: Optional[float] = None
    min_c: Optional[float] = None


@dataclass
class Wind:
    direction_deg: Optional[float] = None
    speed: Optional[float] = None


@dataclass
class Observation:
    station_id: int = 0
    station_code: str = ""
    station_name: str = ""
    station_label: str = ""
    station_name_source: str = "generated"
    lat: float = 0.0
    lon: float = 0.0
    source: str = "snet"
    observed_at: Optional[str] = None
    observed_at_local: Optional[str] = None
    temperature: Temperature = field(default_factory=Temperature)
    wind: Wind = field(default_factory=Wind)


@dataclass
class Station:
    station_id: int = 0
    station_code: str = ""
    station_name: str = ""
    station_label: str = ""
    source: str = "snet"
    lat: float = 0.0
    lon: float = 0.0


@dataclass
class ObservationFeatureRow:
    station_id: int = 0
    station_code: str = ""
    station_name: str = ""
    station_label: str = ""
    source: str = "snet"
    lat: float = 0.0
    lon: float = 0.0
    observed_at: Optional[str] = None
    observed_at_local: Optional[str] = None
    observation_age_minutes: Optional[float] = None
    temperature_current_c: Optional[float] = None
    temperature_max_c: Optional[float] = None
    temperature_min_c: Optional[float] = None
    temperature_diurnal_range_c: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    wind_speed: Optional[float] = None
    has_temperature: bool = False
    has_wind: bool = False
    is_complete: bool = False
    feature_source_version: str = "v1"


@dataclass
class DocumentRecord:
    document_id: str = ""
    document_type: str = ""
    title: Optional[str] = None
    summary: Optional[str] = None
    source: str = "snet"
    url: Optional[str] = None
    issued_at: Optional[str] = None
    last_modified: Optional[str] = None
    content_text: Optional[str] = None


# ── 48-hour Forecast ────────────────────────────────────────

@dataclass
class CityForecast:
    city: str = ""
    max_c: Optional[float] = None
    min_c: Optional[float] = None


@dataclass
class ForecastPeriods:
    morning: Optional[str] = None
    afternoon: Optional[str] = None
    night: Optional[str] = None


@dataclass
class Forecast48h:
    source: str = "snet"
    issued_for: Optional[str] = None
    next_update: Optional[str] = None
    headline: Optional[str] = None
    periods: ForecastPeriods = field(default_factory=ForecastPeriods)
    cities: list[CityForecast] = field(default_factory=list)


# ── PDF Metadata ─────────────────────────────────────────────

@dataclass
class PDFMeta:
    type: str = ""
    source: str = "snet"
    title: Optional[str] = None
    url: Optional[str] = None
    last_modified: Optional[str] = None


# ── Response Metadata ────────────────────────────────────────

@dataclass
class ResponseMeta:
    cached: bool = False
    stale: bool = False
    upstream_status: str = "ok"
    fetched_at: Optional[str] = None


# ── Dashboard Summary ────────────────────────────────────────

@dataclass
class Location:
    lat: float = 0.0
    lon: float = 0.0


@dataclass
class DashboardSummary:
    location: Location = field(default_factory=Location)
    nearest_observation: Optional[Observation] = None
    forecast_48h: Optional[Forecast48h] = None
    weekly_forecast: Optional[PDFMeta] = None
    agro_bulletin: Optional[PDFMeta] = None
    meta: ResponseMeta = field(default_factory=ResponseMeta)


@dataclass
class CanonicalLocationContext:
    location: Location = field(default_factory=Location)
    station: Optional[Station] = None
    observation: Optional[Observation] = None
    features: Optional[ObservationFeatureRow] = None
    documents: list[DocumentRecord] = field(default_factory=list)
    meta: ResponseMeta = field(default_factory=ResponseMeta)
