"""
Time helpers for El Salvador (UTC-6) and SNET epoch conversion.
"""

from datetime import datetime, timezone, timedelta

# El Salvador is always UTC-6 (no daylight saving)
EL_SALVADOR_TZ = timezone(timedelta(hours=-6))


def epoch_ms_to_iso(epoch_ms: int | float | None) -> str | None:
    """Convert a SNET millisecond epoch to an ISO-8601 UTC string."""
    if epoch_ms is None:
        return None
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    return dt.isoformat()


def epoch_ms_to_local(epoch_ms: int | float | None) -> str | None:
    """Convert a SNET millisecond epoch to El Salvador local ISO string."""
    if epoch_ms is None:
        return None
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=EL_SALVADOR_TZ)
    return dt.isoformat()


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def age_minutes_from_iso(iso_timestamp: str | None) -> float | None:
    """Return age in minutes from an ISO-8601 timestamp to now in UTC."""
    if not iso_timestamp:
        return None
    dt = datetime.fromisoformat(iso_timestamp)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    return round(delta.total_seconds() / 60, 2)
