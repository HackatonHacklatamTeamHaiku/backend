"""
Application configuration.

Centralizes all tunables: upstream URLs, cache TTLs, HTTP defaults.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend package directory
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

# IANA timezone when APP_LOCAL_TIMEZONE is missing, empty, or whitespace-only (El Salvador).
DEFAULT_APP_LOCAL_TIMEZONE = "America/El_Salvador"


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
    SNET_RAINFALL_URL = (
        "https://www.snet.gob.sv/googlemaps/arcgis/google/lluvia_data_24h.php"
    )
    SNET_SOIL_URL = (
        "https://geoportal.snet.gob.sv/server/rest/services/clima/"
        "servicio_suelos_pais/MapServer/5/query"
    )
    SNET_BASINS_URL = (
        "https://www.snet.gob.sv/googlemaps/arcgis/google/datos_cuencas.php"
    )
    SNET_CLIMATE_OUTLOOK_URL_TEMPLATE = (
        "https://geoportal.snet.gob.sv/server/rest/services/clima/"
        "perspectivas_clima_servicio/MapServer/{layer_id}/query"
    )
    SNET_MUNICIPAL_BOUNDARIES_URL = (
        "https://geoportal.snet.gob.sv/server/rest/services/"
        "ExposicionASequia/MapServer/0/query"
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
    CACHE_TTL_RAINFALL = int(os.getenv("CACHE_TTL_RAINFALL", "7200"))              # 2 hours
    CACHE_TTL_SOIL = int(os.getenv("CACHE_TTL_SOIL", "86400"))                     # 24 hours
    CACHE_TTL_BASINS = int(os.getenv("CACHE_TTL_BASINS", "86400"))                 # 24 hours
    CACHE_TTL_CLIMATE_OUTLOOK = int(os.getenv("CACHE_TTL_CLIMATE_OUTLOOK", "21600"))  # 6 hours
    CACHE_TTL_FORECAST_DAILY = int(os.getenv("CACHE_TTL_FORECAST_DAILY", "3600"))  # 1 hour
    CACHE_TTL_MUNICIPALITY_LOOKUP = int(os.getenv("CACHE_TTL_MUNICIPALITY_LOOKUP", "86400"))  # 24 hours
    CACHE_TTL_STATION_METADATA = int(os.getenv("CACHE_TTL_STATION_METADATA", "86400"))  # 24 hours
    CACHE_TTL_FORECAST_48H = int(os.getenv("CACHE_TTL_FORECAST_48H", "1800"))      # 30 min
    CACHE_TTL_WEEKLY_PDF = int(os.getenv("CACHE_TTL_WEEKLY_PDF", "21600"))          # 6 hours
    CACHE_TTL_AGRO_PDF = int(os.getenv("CACHE_TTL_AGRO_PDF", "21600"))             # 6 hours

    # ── Supabase REST ─────────────────────────────────────────
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")

    # ── Zavu notifications ────────────────────────────────────
    ZAVUDEV_API_KEY = os.getenv("ZAVUDEV_API_KEY", "")
    ZAVU_DEFAULT_CHANNEL = os.getenv("ZAVU_DEFAULT_CHANNEL", "whatsapp")
    ZAVU_SENDER_ID = os.getenv("ZAVU_SENDER_ID", "")
    ZAVU_WHATSAPP_TEMPLATE_ID = os.getenv("ZAVU_WHATSAPP_TEMPLATE_ID", "")

    # ── Internal jobs ──────────────────────────────────────────
    CRON_SECRET = os.getenv("CRON_SECRET", "")

    # ── Localization (display / calendars; JWT still uses UNIX UTC) ─
    # If APP_LOCAL_TIMEZONE is unset / blank, use El Salvador by default (see DEFAULT_APP_LOCAL_TIMEZONE).
    APP_LOCAL_TIMEZONE = (
        (os.getenv("APP_LOCAL_TIMEZONE") or "").strip()
        or DEFAULT_APP_LOCAL_TIMEZONE
    )

    # ── Auth / JWT ─────────────────────────────────────────────
    AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    AUTH_BYPASS_FOR_TESTING = os.getenv("AUTH_BYPASS_FOR_TESTING", "false").lower() == "true"
    SUPABASE_JWT_ISSUER = os.getenv("SUPABASE_JWT_ISSUER", "")
    SUPABASE_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    SUPABASE_JWKS_TTL = int(os.getenv("SUPABASE_JWKS_TTL", "3600"))
    # Tolerancia de reloj (s) entre emisor Supabase y este servidor para iat/exp (p. ej. NTP +-1–2 s).
    JWT_VALIDATE_LEEWAY_SECONDS = max(0, int(os.getenv("JWT_VALIDATE_LEEWAY_SECONDS", "60")))

    # ── OpenRouter / LLM ──────────────────────────────────────
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "")
    OPENROUTER_FALLBACK_MODELS = os.getenv("OPENROUTER_FALLBACK_MODELS", "openai/gpt-5.4-nano")
    OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "")
    OPENROUTER_TITLE = os.getenv("OPENROUTER_TITLE", "SATO-Agro Backend")
    OPENROUTER_CATEGORIES = os.getenv("OPENROUTER_CATEGORIES", "backend,agriculture")
    OPENROUTER_MAX_TOOL_ROUNDS = int(os.getenv("OPENROUTER_MAX_TOOL_ROUNDS", "4"))
    LLM_SYSTEM_PROMPT_PATH = os.getenv("LLM_SYSTEM_PROMPT_PATH", "")

