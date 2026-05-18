"""
SATO-Agro Flask Backend — Application entry point.

Run with:
    python app.py

Or:
    flask --app app run --debug
"""

from __future__ import annotations

import logging
import sys

from flask import Flask
from flask_cors import CORS

from config import Config
from services.auth import require_api_auth
from services.supabase_rest import SupabaseRestError
from utils.time import now_utc_iso


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Allow browser calls from the deployed app and local development.
    CORS(
        app,
        origins=app.config["CORS_ORIGINS"],
        supports_credentials=True,
        allow_headers=["Authorization", "Content-Type", "Accept"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    app.before_request(require_api_auth)

    @app.errorhandler(SupabaseRestError)
    def handle_supabase_rest_error(error: SupabaseRestError):
        return {
            "data": {"error": str(error), "details": error.payload},
            "meta": {
                "cached": False,
                "stale": False,
                "upstream_status": "configuration_error" if error.status_code is None else "upstream_error",
                "fetched_at": now_utc_iso(),
            },
        }, 503

    # ── Logging ──────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        stream=sys.stdout,
    )

    # ── Register blueprints ──────────────────────────────────
    from routes.health import bp as health_bp
    from routes.auth import bp as auth_bp
    from routes.canonical import bp as canonical_bp
    from routes.ai_tools import bp as ai_tools_bp
    from routes.weather import bp as weather_bp
    from routes.geo import bp as geo_bp
    from routes.risk import bp as risk_bp
    from routes.llm import bp as llm_bp
    from routes.internal_jobs import bp as internal_jobs_bp
    from routes.onboarding import bp as onboarding_bp
    from routes.profile import bp as profile_bp
    from routes.crops import bp as crops_bp
    from routes.plants import bp as plants_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(canonical_bp)
    app.register_blueprint(ai_tools_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(geo_bp)
    app.register_blueprint(risk_bp)
    app.register_blueprint(llm_bp)
    app.register_blueprint(internal_jobs_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(crops_bp)
    app.register_blueprint(plants_bp)

    # ── Root redirect ────────────────────────────────────────
    @app.route("/")
    def root():
        return {
            "service": "sato-agro-backend",
            "version": "1.0.0",
            "endpoints": [
                "/health",
                "/api/weather/observed?lat=&lon=",
                "/api/weather/forecast?lat=&lon=&target_date=",
                "/api/geo/context?lat=&lon=",
                "/api/risk/assessment?crop=&sowing_date=&lat=&lon=",
                "/api/auth/me",
                "/api/profile",
                "/api/plants",
                "/api/crops",
                "/api/onboarding/parcel",
                "/api/llm/context",
                "/api/llm/explain",
                "/api/internal/jobs/daily-risk-alerts",
                "/api/llm/chat",
                "/api/v1/documents/latest",
                "/api/v1/ai/tools/manifest",
                "/api/v1/ai/tools/call",
            ],
        }

    return app


# ── Dev server ───────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
