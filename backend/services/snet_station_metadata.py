"""
Fetch human-readable station metadata from the public SNET station detail page.
"""

from __future__ import annotations

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

from bs4 import BeautifulSoup

from config import Config
from utils.cache import DataCache
from utils.http import session

logger = logging.getLogger(__name__)

_cache = DataCache(ttl=Config.CACHE_TTL_STATION_METADATA, maxsize=4)
_HEADER_RE = re.compile(r"Estación:(?P<id>\d+)\s*(?P<name>.+)")
_COORD_RE = re.compile(
    r"Lat\s+(?P<lat>-?\d+(?:\.\d+)?),\s*Lon\s+(?P<lon>-?\d+(?:\.\d+)?)"
)


def _slugify_station_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown-station"


def _fetch_one(station_id: int) -> dict | None:
    resp = session.get(
        Config.SNET_STATION_DETAIL_URL,
        params={"Estacion": station_id},
        timeout=Config.HTTP_TIMEOUT,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    header = soup.find("th")
    coords = soup.find("b")
    if header is None or coords is None:
        return None

    header_text = html.unescape(header.get_text(" ", strip=True))
    coords_text = html.unescape(coords.get_text(" ", strip=True))

    header_match = _HEADER_RE.search(header_text)
    coords_match = _COORD_RE.search(coords_text)
    if header_match is None or coords_match is None:
        return None

    station_name = header_match.group("name").strip()
    return {
        "station_id": station_id,
        "station_code": f"snet-{station_id}",
        "station_name": station_name,
        "station_slug": _slugify_station_name(station_name),
        "station_label": f"{station_name} weather station",
        "station_name_source": "snet_station_detail",
        "metadata_lat": float(coords_match.group("lat")),
        "metadata_lon": float(coords_match.group("lon")),
    }


def get_many(station_ids: Iterable[int]) -> dict[int, dict]:
    """
    Return station metadata keyed by station_id.

    Results are cached for 24 hours because station names rarely change.
    """
    requested_ids = sorted({sid for sid in station_ids if sid is not None})
    cached_map, _ = _cache.get()
    metadata_map: dict[int, dict] = dict(cached_map or {})
    missing_ids = [sid for sid in requested_ids if sid not in metadata_map]
    if not missing_ids:
        return {sid: metadata_map[sid] for sid in requested_ids if sid in metadata_map}

    fetched: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(missing_ids))) as executor:
        futures = {
            executor.submit(_fetch_one, sid): sid
            for sid in missing_ids
        }
        for future in as_completed(futures):
            sid = futures[future]
            try:
                station_meta = future.result()
            except Exception:
                logger.exception("Failed to fetch station metadata for %s", sid)
                continue
            if station_meta:
                fetched[sid] = station_meta

    if fetched:
        metadata_map.update(fetched)
        _cache.set(metadata_map)

    return {sid: metadata_map[sid] for sid in requested_ids if sid in metadata_map}
