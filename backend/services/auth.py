from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import jwt
import requests
from flask import current_app, g, jsonify, request
from jwt import InvalidTokenError

from config import Config
from services.supabase_rest import rest_insert, rest_select, rest_upsert
from utils.time import now_utc_iso

logger = logging.getLogger(__name__)

_jwks_cache: dict[str, Any] = {"fetched_at": None, "jwks": None}


@dataclass
class AuthError(Exception):
    message: str
    status_code: int = 401
    code: str = "unauthorized"


def require_api_auth():
    if request.method == "OPTIONS":
        return None
    if request.path in {"/", "/health"}:
        return None
    if request.path.startswith("/api/internal/jobs/"):
        return None
    if not request.path.startswith("/api/"):
        return None
    if current_app.config.get("AUTH_BYPASS_FOR_TESTING"):
        g.current_user = _testing_user()
        return None
    if not current_app.config.get("AUTH_ENABLED", True):
        g.current_user = None
        return None
    try:
        g.current_user = resolve_request_user()
    except AuthError as exc:
        return (
            jsonify(
                {
                    "error": exc.message,
                    "code": exc.code,
                    "meta": {
                        "cached": False,
                        "stale": False,
                        "upstream_status": "unauthorized",
                        "fetched_at": now_utc_iso(),
                    },
                }
            ),
            exc.status_code,
        )
    return None


def resolve_request_user() -> dict:
    token = _extract_bearer_token()
    claims = verify_supabase_access_token(token)
    profile = ensure_profile_for_claims(claims)
    return {
        "user_id": claims["sub"],
        "email": claims.get("email"),
        "role": claims.get("role"),
        "claims": claims,
        "profile": profile,
    }


def verify_supabase_access_token(token: str) -> dict:
    supabase_url = (Config.SUPABASE_URL or "").rstrip("/")
    if not supabase_url:
        raise AuthError("Backend auth is not configured: SUPABASE_URL is missing", 503, "auth_not_configured")

    issuer = (Config.SUPABASE_JWT_ISSUER or f"{supabase_url}/auth/v1").rstrip("/")
    audience = (Config.SUPABASE_JWT_AUDIENCE or "").strip()

    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise AuthError(f"Invalid JWT header: {exc}", 401, "invalid_token") from exc

    kid = header.get("kid")
    alg = header.get("alg")
    jwks = _get_cached_jwks()
    signing_key = _resolve_signing_key(jwks, kid, alg)
    if signing_key is None:
        raise AuthError("JWT signing key was not found in Supabase JWKS", 401, "invalid_token")

    try:
        options = {"require": ["exp", "iat", "sub", "iss"]}
        decoded = jwt.decode(
            token,
            signing_key,
            algorithms=[alg] if alg else None,
            audience=audience or None,
            issuer=issuer,
            options=options | {"verify_aud": bool(audience)},
        )
    except InvalidTokenError as exc:
        raise AuthError(f"JWT verification failed: {exc}", 401, "invalid_token") from exc

    if not decoded.get("sub"):
        raise AuthError("JWT is missing sub claim", 401, "invalid_token")
    return decoded


def ensure_profile_for_claims(claims: dict) -> dict | None:
    try:
        existing = rest_select("profiles", {"select": "*", "id": f"eq.{claims['sub']}", "limit": "1"})
        if existing:
            return existing[0]

        user_meta = claims.get("user_metadata") or {}
        full_name = user_meta.get("full_name") or user_meta.get("name")
        display_name = user_meta.get("display_name") or user_meta.get("name")
        phone = claims.get("phone") or user_meta.get("phone")

        created = rest_insert(
            "profiles",
            {
                "id": claims["sub"],
                "full_name": full_name,
                "display_name": display_name,
                "phone": phone,
                "whatsapp_phone": phone,
                "role": "producer",
                "preferred_language": "es",
                "country": "El Salvador",
                "onboarding_completed": False,
            },
        )
        rest_upsert("user_preferences", {"profile_id": claims["sub"]}, on_conflict="profile_id")
        return created[0] if created else None
    except RuntimeError:
        return None
    except Exception:
        logger.exception("Failed to ensure profile for authenticated user")
        return None


def _extract_bearer_token() -> str:
    header = request.headers.get("Authorization", "").strip()
    if not header:
        raise AuthError("Missing Authorization header. Use Bearer <access_token>.", 401, "missing_authorization")
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AuthError("Authorization header must use the Bearer scheme.", 401, "invalid_authorization")
    return parts[1].strip()


def _get_cached_jwks() -> dict:
    fetched_at = _jwks_cache["fetched_at"]
    ttl_seconds = int(Config.SUPABASE_JWKS_TTL)
    if fetched_at and _jwks_cache["jwks"] and datetime.utcnow() - fetched_at < timedelta(seconds=ttl_seconds):
        return _jwks_cache["jwks"]

    supabase_url = (Config.SUPABASE_URL or "").rstrip("/")
    if not supabase_url:
        raise AuthError("Backend auth is not configured: SUPABASE_URL is missing", 503, "auth_not_configured")
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url, timeout=Config.HTTP_TIMEOUT)
        response.raise_for_status()
        jwks = response.json()
    except Exception as exc:
        raise AuthError(f"Unable to fetch Supabase JWKS: {exc}", 503, "jwks_unavailable") from exc

    _jwks_cache["fetched_at"] = datetime.utcnow()
    _jwks_cache["jwks"] = jwks
    return jwks


def _resolve_signing_key(jwks: dict, kid: str | None, alg: str | None):
    for key_data in jwks.get("keys", []):
        if kid and key_data.get("kid") != kid:
            continue
        if alg and key_data.get("alg") not in {None, alg}:
            continue
        return jwt.algorithms.get_default_algorithms()[key_data["alg"]].from_jwk(json.dumps(key_data))
    return None


def _testing_user() -> dict:
    claims = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "testing@satoagro.local",
        "role": "authenticated",
        "user_metadata": {"full_name": "Testing User", "display_name": "Testing User"},
    }
    profile = ensure_profile_for_claims(claims) or {
        "id": claims["sub"],
        "full_name": "Testing User",
        "display_name": "Testing User",
        "role": "producer",
    }
    return {
        "user_id": claims["sub"],
        "email": claims["email"],
        "role": claims["role"],
        "claims": claims,
        "profile": profile,
    }
