"""
Application configuration.

Centralizes all tunables: upstream URLs, cache TTLs, HTTP defaults.
"""

import os


class Config:
    """Base configuration."""

    # ── Flask ────────────────────────────────────────────────
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod")

    # ── Upstream SNET endpoints ──────────────────────────────
    SNET_TEMPERATURE_URL = (
        "https://geoportal.snet.gob.sv/server/rest/services/"
        "TemperaturaActualMaxMin/MapServer/0/query"
    )
    SNET_WIND_URL = (
        "https://geoportal.snet.gob.sv/server/rest/services/"
        "viento_promedio_2horas/FeatureServer/0/query"
    )
    SNET_STATION_DETAIL_URL = (
        "https://www.snet.gob.sv/Geologia/pcbase2/listado.php"
    )
    SNET_FORECAST_48H_URL = (
        "https://www.snet.gob.sv/ver/meteorologia/pronostico/48+horas/"
    )
    SNET_WEEKLY_PDF_PAGE_URL = (
        "https://www.snet.gob.sv/ver/meteorologia/clima/pronostico+semanal/"
    )
    SNET_AGRO_VIEWER_URL = (
        "https://srt.snet.gob.sv/apps/public/viewboletinagro"
    )

    # ── HTTP defaults ────────────────────────────────────────
    HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "10"))
    HTTP_RETRIES = int(os.getenv("HTTP_RETRIES", "2"))

    # ── Cache TTLs (seconds) ─────────────────────────────────
    CACHE_TTL_OBSERVATIONS = int(os.getenv("CACHE_TTL_OBSERVATIONS", "600"))       # 10 min
    CACHE_TTL_STATION_METADATA = int(os.getenv("CACHE_TTL_STATION_METADATA", "86400"))  # 24 hours
    CACHE_TTL_FORECAST_48H = int(os.getenv("CACHE_TTL_FORECAST_48H", "1800"))      # 30 min
    CACHE_TTL_WEEKLY_PDF = int(os.getenv("CACHE_TTL_WEEKLY_PDF", "21600"))          # 6 hours
    CACHE_TTL_AGRO_PDF = int(os.getenv("CACHE_TTL_AGRO_PDF", "21600"))             # 6 hours
