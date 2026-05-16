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


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Enable CORS so the frontend can call the API from any origin
    CORS(app)

    # ── Logging ──────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        stream=sys.stdout,
    )

    # ── Register blueprints ──────────────────────────────────
    from routes.health import bp as health_bp
    from routes.observations import bp as observations_bp
    from routes.forecasts import bp as forecasts_bp
    from routes.agro import bp as agro_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.canonical import bp as canonical_bp
    from routes.ai_tools import bp as ai_tools_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(observations_bp)
    app.register_blueprint(forecasts_bp)
    app.register_blueprint(agro_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(canonical_bp)
    app.register_blueprint(ai_tools_bp)

    # ── Root redirect ────────────────────────────────────────
    @app.route("/")
    def root():
        return {
            "service": "sato-agro-backend",
            "version": "1.0.0",
            "endpoints": [
                "/health",
                "/api/v1/observations/current",
                "/api/v1/observations/nearest?lat=&lon=",
                "/api/v1/forecast/48h",
                "/api/v1/forecast/weekly",
                "/api/v1/agro/latest",
                "/api/v1/dashboard/summary?lat=&lon=",
                "/api/v1/stations",
                "/api/v1/features/current",
                "/api/v1/documents/latest",
                "/api/v1/context/location?lat=&lon=",
                "/api/v1/ai/tools/manifest",
                "/api/v1/ai/tools/call",
            ],
        }

    return app


# ── Dev server ───────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
