from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from services.supabase_rest import SupabaseRestError, rest_insert, rest_select, rest_update, rest_upsert


CROP_CODE_TO_ID = {
    "maiz": 1,
    "maize": 1,
    "frijol": 2,
    "bean": 2,
}

CROP_ID_TO_UI_CODE = {
    1: "maiz",
    2: "frijol",
}

USER_CROP_SELECT = "id,profile_id,crop_type_id,display_name,sowing_date,lat,lon,status,created_at,updated_at"


def get_active_parcel_context(profile_id: str) -> dict[str, Any] | None:
    rows = rest_select(
        "user_crops",
        {
            "select": USER_CROP_SELECT,
            "profile_id": f"eq.{profile_id}",
            "status": "eq.active",
            "order": "updated_at.desc,created_at.desc",
            "limit": "1",
        },
    )
    return _serialize_user_crop(rows[0]) if rows else None


def list_crop_cycles(profile_id: str) -> list[dict[str, Any]]:
    rows = rest_select(
        "user_crops",
        {
            "select": USER_CROP_SELECT,
            "profile_id": f"eq.{profile_id}",
            "status": "neq.archived",
            "order": "updated_at.desc,created_at.desc",
        },
    )
    return [_serialize_user_crop(row) for row in rows]


def create_plant_cycle(
    *,
    profile_id: str,
    crop: str,
    sowing_date: date,
    lat: float,
    lon: float,
    plant_name: str | None = None,
    farm_name: str = "Finca principal",
) -> dict[str, Any]:
    del farm_name
    return _create_or_reuse_user_crop(
        profile_id=profile_id,
        crop=crop,
        sowing_date=sowing_date,
        lat=lat,
        lon=lon,
        display_name=plant_name,
    )


def rename_plant_cycle(*, profile_id: str, crop_cycle_id: str, plant_name: str) -> dict[str, Any] | None:
    updated = rest_update(
        "user_crops",
        {"id": crop_cycle_id, "profile_id": profile_id, "status": "neq.archived"},
        {"display_name": plant_name},
    )
    return _serialize_user_crop(updated[0]) if updated else None


def archive_plant_cycle(*, profile_id: str, crop_cycle_id: str) -> dict[str, Any] | None:
    updated = rest_update(
        "user_crops",
        {"id": crop_cycle_id, "profile_id": profile_id, "status": "neq.archived"},
        {"status": "archived"},
    )
    if not updated:
        return None
    archived_id = _json_value(updated[0]["id"])
    return {"user_crop_id": archived_id, "crop_cycle_id": archived_id, "status": "archived"}


def create_crop_cycle(
    *,
    profile_id: str,
    crop: str,
    sowing_date: date,
    lat: float,
    lon: float,
    crop_name: str | None = None,
) -> dict[str, Any]:
    return create_plant_cycle(
        profile_id=profile_id,
        crop=crop,
        sowing_date=sowing_date,
        lat=lat,
        lon=lon,
        plant_name=crop_name,
    )


def rename_crop_cycle(*, profile_id: str, crop_cycle_id: str, crop_name: str) -> dict[str, Any] | None:
    return rename_plant_cycle(profile_id=profile_id, crop_cycle_id=crop_cycle_id, plant_name=crop_name)


archive_crop_cycle = archive_plant_cycle


def save_onboarding_parcel(
    *,
    profile_id: str,
    crop: str,
    sowing_date: date,
    lat: float,
    lon: float,
    farm_name: str = "Finca principal",
    plot_name: str = "Parcela principal",
) -> dict[str, Any]:
    del farm_name, plot_name
    return _create_or_reuse_user_crop(
        profile_id=profile_id,
        crop=crop,
        sowing_date=sowing_date,
        lat=lat,
        lon=lon,
    )


def _create_or_reuse_user_crop(
    *,
    profile_id: str,
    crop: str,
    sowing_date: date,
    lat: float,
    lon: float,
    display_name: str | None = None,
) -> dict[str, Any]:
    crop_type_id = CROP_CODE_TO_ID[crop]

    rest_update(
        "profiles",
        {"id": profile_id},
        {"default_lat": lat, "default_lon": lon, "onboarding_completed": True},
        return_representation=False,
    )
    existing = _find_active_user_crop(
        profile_id=profile_id,
        crop_type_id=crop_type_id,
        sowing_date=sowing_date,
        lat=lat,
        lon=lon,
    )
    if existing:
        if display_name and display_name != existing.get("display_name"):
            updated = rest_update(
                "user_crops",
                {"id": existing["id"], "profile_id": profile_id, "status": "eq.active"},
                {"display_name": display_name},
            )
            existing = updated[0] if updated else existing
        _upsert_crop_interest(profile_id=profile_id, crop_type_id=crop_type_id)
        return _serialize_user_crop(existing)

    try:
        created = rest_insert(
            "user_crops",
            {
                "profile_id": profile_id,
                "crop_type_id": crop_type_id,
                "sowing_date": sowing_date,
                "lat": lat,
                "lon": lon,
                "display_name": display_name,
                "status": "active",
            },
        )
    except SupabaseRestError as exc:
        if exc.status_code != 409:
            raise
        existing = _find_active_user_crop(
            profile_id=profile_id,
            crop_type_id=crop_type_id,
            sowing_date=sowing_date,
            lat=lat,
            lon=lon,
        )
        if not existing:
            raise
        created = [existing]

    _upsert_crop_interest(profile_id=profile_id, crop_type_id=crop_type_id)
    return _serialize_user_crop(created[0])


def _find_active_user_crop(
    *,
    profile_id: str,
    crop_type_id: int,
    sowing_date: date,
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    rows = rest_select(
        "user_crops",
        {
            "select": USER_CROP_SELECT,
            "profile_id": f"eq.{profile_id}",
            "crop_type_id": f"eq.{crop_type_id}",
            "sowing_date": f"eq.{sowing_date.isoformat()}",
            "lat": f"eq.{_coordinate_filter_value(lat)}",
            "lon": f"eq.{_coordinate_filter_value(lon)}",
            "status": "eq.active",
            "order": "updated_at.desc,created_at.desc",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


def _upsert_crop_interest(*, profile_id: str, crop_type_id: int) -> None:
    rest_upsert(
        "user_crop_interests",
        {"profile_id": profile_id, "crop_type_id": crop_type_id, "is_primary": True},
        on_conflict="profile_id,crop_type_id",
        return_representation=False,
    )


def _serialize_user_crop(user_crop: dict[str, Any]) -> dict[str, Any]:
    crop = CROP_ID_TO_UI_CODE.get(int(user_crop["crop_type_id"]), "maiz")
    sowing_date = user_crop["sowing_date"]
    crop_id = _json_value(user_crop["id"])
    display_name = user_crop.get("display_name") or _default_crop_name(crop, sowing_date)
    return {
        "user_crop_id": crop_id,
        "crop_cycle_id": crop_id,
        "farm_id": None,
        "farm_name": None,
        "plot_id": None,
        "plot_name": None,
        "plant_name": display_name,
        "crop_name": display_name,
        "lat": _json_value(user_crop.get("lat")),
        "lon": _json_value(user_crop.get("lon")),
        "crop": crop,
        "sowing_date": _json_value(sowing_date),
        "status": user_crop.get("status"),
    }


def _default_crop_name(crop: str, sowing_date: date | str) -> str:
    crop_label = "Maiz" if crop in {"maiz", "maize"} else "Frijol"
    return f"{crop_label} {_json_value(sowing_date)}"


def _coordinate_filter_value(value: float) -> str:
    return f"{value:.6f}"


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value) if value is not None else None
