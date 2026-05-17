from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from services.supabase_rest import rest_insert, rest_select, rest_update, rest_upsert


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


def get_active_parcel_context(profile_id: str) -> dict[str, Any] | None:
    rows = rest_select(
        "crop_cycles",
        {
            "select": "id,plot_id,crop_type_id,season_label,sowing_date,status,created_at,updated_at",
            "owner_profile_id": f"eq.{profile_id}",
            "status": "eq.active",
            "order": "updated_at.desc,created_at.desc",
            "limit": "1",
        },
    )
    return _serialize_cycle(rows[0]) if rows else None


def list_crop_cycles(profile_id: str) -> list[dict[str, Any]]:
    rows = rest_select(
        "crop_cycles",
        {
            "select": "id,plot_id,crop_type_id,season_label,sowing_date,status,created_at,updated_at",
            "owner_profile_id": f"eq.{profile_id}",
            "status": "neq.archived",
            "order": "updated_at.desc,created_at.desc",
        },
    )
    return [_serialize_cycle(row) for row in rows]


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
    crop_type_id = CROP_CODE_TO_ID[crop]
    safe_plant_name = plant_name or _default_crop_name(crop, sowing_date)

    rest_update(
        "profiles",
        {"id": profile_id},
        {"default_lat": lat, "default_lon": lon, "onboarding_completed": True},
        return_representation=False,
    )
    farm_id = _get_or_create_farm(profile_id=profile_id, farm_name=farm_name, lat=lat, lon=lon)
    plot_id = _get_or_create_primary_plot(farm_id=farm_id, lat=lat, lon=lon)
    created = rest_insert(
        "crop_cycles",
        {
            "plot_id": plot_id,
            "owner_profile_id": profile_id,
            "crop_type_id": crop_type_id,
            "season_label": safe_plant_name,
            "sowing_date": sowing_date,
            "status": "active",
        },
    )
    _upsert_crop_interest(profile_id=profile_id, crop_type_id=crop_type_id)
    return _serialize_cycle(created[0])


def rename_plant_cycle(*, profile_id: str, crop_cycle_id: str, plant_name: str) -> dict[str, Any] | None:
    updated = rest_update(
        "crop_cycles",
        {"id": crop_cycle_id, "owner_profile_id": profile_id, "status": "neq.archived"},
        {"season_label": plant_name},
    )
    return _serialize_cycle(updated[0]) if updated else None


def archive_plant_cycle(*, profile_id: str, crop_cycle_id: str) -> dict[str, Any] | None:
    updated = rest_update(
        "crop_cycles",
        {"id": crop_cycle_id, "owner_profile_id": profile_id, "status": "neq.archived"},
        {"status": "archived"},
    )
    if not updated:
        return None
    return {"crop_cycle_id": _json_value(updated[0]["id"]), "status": "archived"}


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
    crop_type_id = CROP_CODE_TO_ID[crop]

    rest_update(
        "profiles",
        {"id": profile_id},
        {"default_lat": lat, "default_lon": lon, "onboarding_completed": True},
        return_representation=False,
    )
    farm_id = _get_or_create_farm(profile_id=profile_id, farm_name=farm_name, lat=lat, lon=lon)
    plot_id = _get_or_create_plot(farm_id=farm_id, plot_name=plot_name, lat=lat, lon=lon)
    crop_cycle_id = _get_or_create_crop_cycle(
        profile_id=profile_id,
        plot_id=plot_id,
        crop_type_id=crop_type_id,
        sowing_date=sowing_date,
    )
    _upsert_crop_interest(profile_id=profile_id, crop_type_id=crop_type_id)
    return _get_crop_cycle_by_id(profile_id=profile_id, crop_cycle_id=crop_cycle_id)


def _get_or_create_farm(*, profile_id: str, farm_name: str, lat: float, lon: float) -> str:
    rows = rest_select(
        "farms",
        {
            "select": "id",
            "owner_profile_id": f"eq.{profile_id}",
            "order": "created_at.asc",
            "limit": "1",
        },
    )
    if rows:
        farm_id = str(rows[0]["id"])
        rest_update(
            "farms",
            {"id": farm_id},
            {"farm_name": farm_name, "centroid_lat": lat, "centroid_lon": lon},
            return_representation=False,
        )
        return farm_id

    created = rest_insert(
        "farms",
        {"owner_profile_id": profile_id, "farm_name": farm_name, "centroid_lat": lat, "centroid_lon": lon},
    )
    return str(created[0]["id"])


def _get_or_create_plot(*, farm_id: str, plot_name: str, lat: float, lon: float) -> str:
    rows = rest_select(
        "plots",
        {"select": "id", "farm_id": f"eq.{farm_id}", "order": "created_at.asc", "limit": "1"},
    )
    if rows:
        plot_id = str(rows[0]["id"])
        rest_update(
            "plots",
            {"id": plot_id},
            {"plot_name": plot_name, "centroid_lat": lat, "centroid_lon": lon},
            return_representation=False,
        )
        return plot_id

    created = rest_insert(
        "plots",
        {"farm_id": farm_id, "plot_name": plot_name, "centroid_lat": lat, "centroid_lon": lon},
    )
    return str(created[0]["id"])


def _get_or_create_primary_plot(*, farm_id: str, lat: float, lon: float) -> str:
    rows = rest_select(
        "plots",
        {"select": "id", "farm_id": f"eq.{farm_id}", "order": "created_at.asc", "limit": "1"},
    )
    if rows:
        plot_id = str(rows[0]["id"])
        rest_update(
            "plots",
            {"id": plot_id},
            {"centroid_lat": lat, "centroid_lon": lon},
            return_representation=False,
        )
        return plot_id

    created = rest_insert(
        "plots",
        {"farm_id": farm_id, "plot_name": "Parcela principal", "centroid_lat": lat, "centroid_lon": lon},
    )
    return str(created[0]["id"])


def _get_or_create_crop_cycle(*, profile_id: str, plot_id: str, crop_type_id: int, sowing_date: date) -> str:
    rows = rest_select(
        "crop_cycles",
        {
            "select": "id",
            "owner_profile_id": f"eq.{profile_id}",
            "plot_id": f"eq.{plot_id}",
            "crop_type_id": f"eq.{crop_type_id}",
            "sowing_date": f"eq.{sowing_date.isoformat()}",
            "status": "eq.active",
            "order": "updated_at.desc,created_at.desc",
            "limit": "1",
        },
    )
    if rows:
        return str(rows[0]["id"])

    rest_update(
        "crop_cycles",
        {"owner_profile_id": profile_id, "plot_id": plot_id, "status": "eq.active"},
        {"status": "archived"},
        return_representation=False,
    )
    created = rest_insert(
        "crop_cycles",
        {
            "plot_id": plot_id,
            "owner_profile_id": profile_id,
            "crop_type_id": crop_type_id,
            "sowing_date": sowing_date,
            "status": "active",
        },
    )
    return str(created[0]["id"])


def _get_crop_cycle_by_id(*, profile_id: str, crop_cycle_id: str) -> dict[str, Any] | None:
    rows = rest_select(
        "crop_cycles",
        {
            "select": "id,plot_id,crop_type_id,season_label,sowing_date,status",
            "id": f"eq.{crop_cycle_id}",
            "owner_profile_id": f"eq.{profile_id}",
            "limit": "1",
        },
    )
    return _serialize_cycle(rows[0]) if rows else None


def _upsert_crop_interest(*, profile_id: str, crop_type_id: int) -> None:
    rest_upsert(
        "user_crop_interests",
        {"profile_id": profile_id, "crop_type_id": crop_type_id, "is_primary": True},
        on_conflict="profile_id,crop_type_id",
        return_representation=False,
    )


def _serialize_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    plot = _get_plot(cycle.get("plot_id"))
    farm = _get_farm(plot.get("farm_id") if plot else None)
    crop = CROP_ID_TO_UI_CODE.get(int(cycle["crop_type_id"]), "maiz")
    sowing_date = cycle["sowing_date"]
    return {
        "farm_id": _json_value(farm.get("id") if farm else None),
        "farm_name": farm.get("farm_name") if farm else None,
        "plot_id": _json_value(plot.get("id") if plot else cycle.get("plot_id")),
        "plot_name": plot.get("plot_name") if plot else None,
        "plant_name": cycle.get("season_label") or _default_crop_name(crop, sowing_date),
        "crop_name": cycle.get("season_label") or (plot.get("plot_name") if plot else None) or _default_crop_name(crop, sowing_date),
        "lat": _json_value(plot.get("centroid_lat") if plot else None),
        "lon": _json_value(plot.get("centroid_lon") if plot else None),
        "crop_cycle_id": _json_value(cycle["id"]),
        "crop": crop,
        "sowing_date": _json_value(sowing_date),
        "status": cycle.get("status"),
    }


def _get_plot(plot_id: Any) -> dict[str, Any] | None:
    if not plot_id:
        return None
    rows = rest_select(
        "plots",
        {"select": "id,farm_id,plot_name,centroid_lat,centroid_lon", "id": f"eq.{plot_id}", "limit": "1"},
    )
    return rows[0] if rows else None


def _get_farm(farm_id: Any) -> dict[str, Any] | None:
    if not farm_id:
        return None
    rows = rest_select("farms", {"select": "id,farm_name", "id": f"eq.{farm_id}", "limit": "1"})
    return rows[0] if rows else None


def _default_crop_name(crop: str, sowing_date: date | str) -> str:
    crop_label = "Maiz" if crop in {"maiz", "maize"} else "Frijol"
    return f"{crop_label} {_json_value(sowing_date)}"


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value) if value is not None else None
