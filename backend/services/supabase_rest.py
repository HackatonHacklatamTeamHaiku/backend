from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

import requests
from flask import current_app


class SupabaseRestError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def rest_select(table: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return _request("GET", table, params=params)


def rest_insert(table: str, payload: dict[str, Any], *, return_representation: bool = True) -> list[dict[str, Any]]:
    return _request(
        "POST",
        table,
        json_payload=_json_payload(payload),
        prefer=_prefer(return_representation),
    )


def rest_update(
    table: str,
    filters: dict[str, Any],
    payload: dict[str, Any],
    *,
    return_representation: bool = True,
) -> list[dict[str, Any]]:
    return _request(
        "PATCH",
        table,
        params=_filters(filters),
        json_payload=_json_payload(payload),
        prefer=_prefer(return_representation),
    )


def rest_upsert(
    table: str,
    payload: dict[str, Any],
    *,
    on_conflict: str | None = None,
    return_representation: bool = True,
) -> list[dict[str, Any]]:
    params = {"on_conflict": on_conflict} if on_conflict else None
    prefer = "resolution=merge-duplicates"
    if return_representation:
        prefer = f"{prefer},return=representation"
    return _request(
        "POST",
        table,
        params=params,
        json_payload=_json_payload(payload),
        prefer=prefer,
    )


def rest_delete(table: str, filters: dict[str, Any], *, return_representation: bool = False) -> list[dict[str, Any]]:
    return _request(
        "DELETE",
        table,
        params=_filters(filters),
        prefer=_prefer(return_representation),
    )


def rest_available() -> bool:
    try:
        rest_select("crop_types", {"select": "id", "limit": "1"})
        return True
    except Exception:
        return False


def _request(
    method: str,
    table: str,
    *,
    params: dict[str, Any] | None = None,
    json_payload: Any = None,
    prefer: str | None = None,
) -> list[dict[str, Any]]:
    supabase_url = (current_app.config.get("SUPABASE_URL") or "").rstrip("/")
    service_key = current_app.config.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not supabase_url or not service_key:
        raise SupabaseRestError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer

    response = requests.request(
        method,
        f"{supabase_url}/rest/v1/{table}",
        headers=headers,
        params=params,
        json=json_payload,
        timeout=current_app.config.get("HTTP_TIMEOUT", 10),
    )
    if response.status_code >= 400:
        raise SupabaseRestError(
            f"Supabase REST {method} {table} failed with status {response.status_code}",
            response.status_code,
            _response_payload(response),
        )
    if response.status_code == 204 or not response.content:
        return []
    payload = _response_payload(response)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    return []


def _filters(filters: dict[str, Any]) -> dict[str, Any]:
    return {key: value if isinstance(value, str) and "." in value else f"eq.{value}" for key, value in filters.items()}


def _prefer(return_representation: bool) -> str:
    return "return=representation" if return_representation else "return=minimal"


def _json_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_payload(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def _response_payload(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
