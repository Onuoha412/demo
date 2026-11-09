from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


UTC = timezone.utc


class InvalidTimeZone(ValueError):
    """Raised when an IANA timezone cannot be loaded."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime values must include a timezone.")
    return value.astimezone(UTC)


def get_timezone(name: str) -> ZoneInfo:
    normalized = name.strip()
    try:
        return ZoneInfo(normalized)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise InvalidTimeZone(f"Unknown IANA timezone: {name}") from error


def localize(value: datetime, timezone_name: str) -> datetime:
    return as_utc(value).astimezone(get_timezone(timezone_name))


def local_to_utc(value: datetime, timezone_name: str) -> datetime:
    """Convert a wall-clock value and reject DST gaps or ambiguous times."""
    if value.tzinfo is not None and value.utcoffset() is not None:
        return as_utc(value)
    zone = get_timezone(timezone_name)
    candidates = []
    for fold in (0, 1):
        candidate = value.replace(tzinfo=zone, fold=fold)
        round_trip = candidate.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        if round_trip == value:
            candidates.append(candidate)
    if not candidates:
        raise ValueError(
            f"Local time {value.isoformat()} does not exist in {timezone_name}."
        )
    if len(candidates) > 1 and candidates[0].utcoffset() != candidates[1].utcoffset():
        raise ValueError(
            f"Local time {value.isoformat()} is ambiguous in {timezone_name}; "
            "provide an explicit UTC offset."
        )
    return candidates[0].astimezone(UTC)


def effective_timezone(
    organization_timezone: str,
    branch_timezone: str | None = None,
) -> str:
    """Return a validated branch override or its organization's timezone."""
    selected = (branch_timezone or organization_timezone).strip()
    get_timezone(selected)
    return selected


def countdown(target: datetime, now: datetime | None = None) -> timedelta:
    return max(as_utc(target) - as_utc(now or utc_now()), timedelta(0))


def duration_minutes(start: datetime, end: datetime | None = None) -> int:
    finish = as_utc(end or utc_now())
    return max(0, round((finish - as_utc(start)).total_seconds() / 60))


@dataclass(frozen=True)
class TimeSnapshot:
    server_time: datetime
    timezone: str
    local_time: datetime


def snapshot(timezone_name: str = "UTC", now: datetime | None = None) -> TimeSnapshot:
    current = as_utc(now or utc_now())
    get_timezone(timezone_name)
    return TimeSnapshot(
        server_time=current,
        timezone=timezone_name,
        local_time=current.astimezone(get_timezone(timezone_name)),
    )
