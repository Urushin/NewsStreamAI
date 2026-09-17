"""UTC timestamp helpers. Unknown business timestamps remain unknown."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_iso8601(value: datetime | None) -> str | None:
    """Serialize a datetime as UTC, preserving ``None`` for unknown values."""
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("A persisted business timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
