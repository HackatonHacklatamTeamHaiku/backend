from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg2.extras import RealDictRow

from services.database import get_dict_cursor


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
    with get_dict_cursor() as cur:
        cur.execute(
            """
            SELECT
                farms.id AS farm_id,
                farms.farm_name,
                plots.id AS plot_id,
                plots.plot_name,
                plots.centroid_lat,
                plots.centroid_lon,
                crop_cycles.id AS crop_cycle_id,
                crop_cycles.crop_type_id,
                crop_cycles.sowing_date,
                crop_cycles.status
            FROM crop_cycles
            JOIN plots ON plots.id = crop_cycles.plot_id
            JOIN farms ON farms.id = plots.farm_id
            WHERE crop_cycles.owner_profile_id = %s
              AND crop_cycles.status = 'active'
            ORDER BY crop_cycles.updated_at DESC, crop_cycles.created_at DESC
            LIMIT 1
            """,
            (profile_id,),
        )
        row = cur.fetchone()
        return _serialize_parcel_context(row) if row else None


def list_crop_cycles(profile_id: str) -> list[dict[str, Any]]:
    with get_dict_cursor() as cur:
        cur.execute(
            """
            SELECT
                farms.id AS farm_id,
                farms.farm_name,
                plots.id AS plot_id,
                plots.plot_name,
                plots.centroid_lat,
                plots.centroid_lon,
                crop_cycles.id AS crop_cycle_id,
                crop_cycles.crop_type_id,
                crop_cycles.season_label,
                crop_cycles.sowing_date,
                crop_cycles.status
            FROM crop_cycles
            JOIN plots ON plots.id = crop_cycles.plot_id
            JOIN farms ON farms.id = plots.farm_id
            WHERE crop_cycles.owner_profile_id = %s
              AND crop_cycles.status <> 'archived'
            ORDER BY crop_cycles.updated_at DESC, crop_cycles.created_at DESC
            """,
            (profile_id,),
        )
        return [_serialize_parcel_context(row) for row in cur.fetchall()]


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

    with get_dict_cursor() as cur:
        cur.execute(
            """
            UPDATE profiles
            SET default_lat = COALESCE(default_lat, %s),
                default_lon = COALESCE(default_lon, %s),
                onboarding_completed = true
            WHERE id = %s
            """,
            (lat, lon, profile_id),
        )
        farm_id = _get_or_create_farm(
            cur,
            profile_id=profile_id,
            farm_name=farm_name,
            lat=lat,
            lon=lon,
        )
        plot_id = _get_or_create_primary_plot(
            cur,
            farm_id=farm_id,
            lat=lat,
            lon=lon,
        )
        cur.execute(
            """
            INSERT INTO crop_cycles (
                plot_id,
                owner_profile_id,
                crop_type_id,
                season_label,
                sowing_date,
                status
            )
            VALUES (%s, %s, %s, %s, %s, 'active')
            RETURNING id
            """,
            (plot_id, profile_id, crop_type_id, safe_plant_name, sowing_date),
        )
        crop_cycle_id = str(cur.fetchone()["id"])
        _upsert_crop_interest(cur, profile_id=profile_id, crop_type_id=crop_type_id)
        return _get_crop_cycle_by_id(cur, profile_id=profile_id, crop_cycle_id=crop_cycle_id)


def rename_plant_cycle(*, profile_id: str, crop_cycle_id: str, plant_name: str) -> dict[str, Any] | None:
    with get_dict_cursor() as cur:
        cur.execute(
            """
            UPDATE crop_cycles
            SET season_label = %s
            WHERE id = %s
              AND owner_profile_id = %s
              AND status <> 'archived'
            RETURNING plot_id
            """,
            (plant_name, crop_cycle_id, profile_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return _get_crop_cycle_by_id(cur, profile_id=profile_id, crop_cycle_id=crop_cycle_id)


def archive_plant_cycle(*, profile_id: str, crop_cycle_id: str) -> dict[str, Any] | None:
    with get_dict_cursor() as cur:
        cur.execute(
            """
            UPDATE crop_cycles
            SET status = 'archived'
            WHERE id = %s
              AND owner_profile_id = %s
              AND status <> 'archived'
            RETURNING id
            """,
            (crop_cycle_id, profile_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"crop_cycle_id": str(row["id"]), "status": "archived"}


# Backwards-compatible service aliases while callers migrate from crop wording to plant wording.
create_crop_cycle = create_plant_cycle
rename_crop_cycle = rename_plant_cycle
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

    with get_dict_cursor() as cur:
        cur.execute(
            """
            UPDATE profiles
            SET default_lat = %s,
                default_lon = %s,
                onboarding_completed = true
            WHERE id = %s
            """,
            (lat, lon, profile_id),
        )

        farm_id = _get_or_create_farm(
            cur,
            profile_id=profile_id,
            farm_name=farm_name,
            lat=lat,
            lon=lon,
        )
        plot_id = _get_or_create_plot(
            cur,
            farm_id=farm_id,
            plot_name=plot_name,
            lat=lat,
            lon=lon,
        )
        crop_cycle_id = _get_or_create_crop_cycle(
            cur,
            profile_id=profile_id,
            plot_id=plot_id,
            crop_type_id=crop_type_id,
            sowing_date=sowing_date,
        )

        cur.execute(
            """
            INSERT INTO user_crop_interests (profile_id, crop_type_id, is_primary)
            VALUES (%s, %s, true)
            ON CONFLICT (profile_id, crop_type_id) DO UPDATE
            SET is_primary = true
            """,
            (profile_id, crop_type_id),
        )

        cur.execute(
            """
            SELECT
                farms.id AS farm_id,
                farms.farm_name,
                plots.id AS plot_id,
                plots.plot_name,
                plots.centroid_lat,
                plots.centroid_lon,
                crop_cycles.id AS crop_cycle_id,
                crop_cycles.crop_type_id,
                crop_cycles.sowing_date,
                crop_cycles.status
            FROM crop_cycles
            JOIN plots ON plots.id = crop_cycles.plot_id
            JOIN farms ON farms.id = plots.farm_id
            WHERE crop_cycles.id = %s
            """,
            (crop_cycle_id,),
        )
        row = cur.fetchone()
        return _serialize_parcel_context(row)


def _get_or_create_farm(cur, *, profile_id: str, farm_name: str, lat: float, lon: float) -> str:
    cur.execute(
        """
        SELECT id
        FROM farms
        WHERE owner_profile_id = %s
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (profile_id,),
    )
    row = cur.fetchone()
    if row:
        farm_id = str(row["id"])
        cur.execute(
            """
            UPDATE farms
            SET farm_name = COALESCE(NULLIF(%s, ''), farm_name),
                centroid_lat = %s,
                centroid_lon = %s
            WHERE id = %s
            """,
            (farm_name, lat, lon, farm_id),
        )
        return farm_id

    cur.execute(
        """
        INSERT INTO farms (owner_profile_id, farm_name, centroid_lat, centroid_lon)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (profile_id, farm_name, lat, lon),
    )
    return str(cur.fetchone()["id"])


def _get_or_create_plot(cur, *, farm_id: str, plot_name: str, lat: float, lon: float) -> str:
    cur.execute(
        """
        SELECT id
        FROM plots
        WHERE farm_id = %s
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (farm_id,),
    )
    row = cur.fetchone()
    if row:
        plot_id = str(row["id"])
        cur.execute(
            """
            UPDATE plots
            SET plot_name = COALESCE(NULLIF(%s, ''), plot_name),
                centroid_lat = %s,
                centroid_lon = %s
            WHERE id = %s
            """,
            (plot_name, lat, lon, plot_id),
        )
        return plot_id

    cur.execute(
        """
        INSERT INTO plots (farm_id, plot_name, centroid_lat, centroid_lon)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (farm_id, plot_name, lat, lon),
    )
    return str(cur.fetchone()["id"])


def _get_or_create_primary_plot(cur, *, farm_id: str, lat: float, lon: float) -> str:
    cur.execute(
        """
        SELECT id
        FROM plots
        WHERE farm_id = %s
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (farm_id,),
    )
    row = cur.fetchone()
    if row:
        plot_id = str(row["id"])
        cur.execute(
            """
            UPDATE plots
            SET centroid_lat = %s,
                centroid_lon = %s
            WHERE id = %s
            """,
            (lat, lon, plot_id),
        )
        return plot_id

    cur.execute(
        """
        INSERT INTO plots (farm_id, plot_name, centroid_lat, centroid_lon)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (farm_id, "Parcela principal", lat, lon),
    )
    return str(cur.fetchone()["id"])


def _get_or_create_crop_cycle(
    cur,
    *,
    profile_id: str,
    plot_id: str,
    crop_type_id: int,
    sowing_date: date,
) -> str:
    cur.execute(
        """
        SELECT id
        FROM crop_cycles
        WHERE owner_profile_id = %s
          AND plot_id = %s
          AND crop_type_id = %s
          AND sowing_date = %s
          AND status = 'active'
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
        """,
        (profile_id, plot_id, crop_type_id, sowing_date),
    )
    row = cur.fetchone()
    if row:
        return str(row["id"])

    cur.execute(
        """
        UPDATE crop_cycles
        SET status = 'archived'
        WHERE owner_profile_id = %s
          AND plot_id = %s
          AND status = 'active'
        """,
        (profile_id, plot_id),
    )
    cur.execute(
        """
        INSERT INTO crop_cycles (
            plot_id,
            owner_profile_id,
            crop_type_id,
            sowing_date,
            status
        )
        VALUES (%s, %s, %s, %s, 'active')
        RETURNING id
        """,
        (plot_id, profile_id, crop_type_id, sowing_date),
    )
    return str(cur.fetchone()["id"])


def _get_crop_cycle_by_id(cur, *, profile_id: str, crop_cycle_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT
            farms.id AS farm_id,
            farms.farm_name,
            plots.id AS plot_id,
            plots.plot_name,
            plots.centroid_lat,
            plots.centroid_lon,
            crop_cycles.id AS crop_cycle_id,
            crop_cycles.crop_type_id,
            crop_cycles.season_label,
            crop_cycles.sowing_date,
            crop_cycles.status
        FROM crop_cycles
        JOIN plots ON plots.id = crop_cycles.plot_id
        JOIN farms ON farms.id = plots.farm_id
        WHERE crop_cycles.id = %s
          AND crop_cycles.owner_profile_id = %s
        """,
        (crop_cycle_id, profile_id),
    )
    row = cur.fetchone()
    return _serialize_parcel_context(row) if row else None


def _upsert_crop_interest(cur, *, profile_id: str, crop_type_id: int) -> None:
    cur.execute(
        """
        INSERT INTO user_crop_interests (profile_id, crop_type_id, is_primary)
        VALUES (%s, %s, true)
        ON CONFLICT (profile_id, crop_type_id) DO UPDATE
        SET is_primary = true
        """,
        (profile_id, crop_type_id),
    )


def _default_crop_name(crop: str, sowing_date: date) -> str:
    crop_label = "Maiz" if crop in {"maiz", "maize"} else "Frijol"
    return f"{crop_label} {sowing_date.isoformat()}"


def _serialize_parcel_context(row: RealDictRow | dict[str, Any]) -> dict[str, Any]:
    crop = CROP_ID_TO_UI_CODE.get(int(row["crop_type_id"]), "maiz")
    return {
        "farm_id": _json_value(row["farm_id"]),
        "farm_name": row.get("farm_name"),
        "plot_id": _json_value(row["plot_id"]),
        "plot_name": row.get("plot_name"),
        "plant_name": row.get("season_label") or _default_crop_name(crop, row["sowing_date"]),
        "crop_name": row.get("season_label") or row.get("plot_name") or _default_crop_name(crop, row["sowing_date"]),
        "lat": _json_value(row.get("centroid_lat")),
        "lon": _json_value(row.get("centroid_lon")),
        "crop_cycle_id": _json_value(row["crop_cycle_id"]),
        "crop": crop,
        "sowing_date": _json_value(row["sowing_date"]),
        "status": row.get("status"),
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value) if value is not None else None
