from datetime import datetime, timedelta, timezone

import pytest

from app.services.time_engine import (
    InvalidTimeZone,
    as_utc,
    countdown,
    duration_minutes,
    get_timezone,
    localize,
    local_to_utc,
    effective_timezone,
    snapshot,
    utc_now,
)


def test_utc_now_is_timezone_aware() -> None:
    assert utc_now().tzinfo == timezone.utc


def test_lagos_conversion_is_correct() -> None:
    value = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    assert localize(value, "Africa/Lagos").hour == 13


def test_dst_transition_uses_iana_rules() -> None:
    before = localize(datetime(2026, 3, 8, 6, 30, tzinfo=timezone.utc), "America/New_York")
    after = localize(datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc), "America/New_York")
    assert before.utcoffset() == timedelta(hours=-5)
    assert after.utcoffset() == timedelta(hours=-4)


def test_naive_datetimes_are_rejected_for_persistence() -> None:
    with pytest.raises(ValueError, match="timezone"):
        as_utc(datetime(2026, 1, 1))


def test_invalid_timezone_is_rejected() -> None:
    with pytest.raises(InvalidTimeZone):
        get_timezone("Not/A_Timezone")


def test_countdown_and_duration_are_clamped_and_in_minutes() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert countdown(now - timedelta(minutes=2), now) == timedelta(0)
    assert duration_minutes(now, now + timedelta(minutes=7, seconds=30)) == 8
    assert snapshot("Africa/Lagos", now).local_time.hour == 1


def test_local_time_conversion_rejects_dst_gap_and_ambiguity() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        local_to_utc(datetime(2026, 3, 8, 2, 30), "America/New_York")
    with pytest.raises(ValueError, match="ambiguous"):
        local_to_utc(datetime(2026, 11, 1, 1, 30), "America/New_York")


def test_branch_timezone_override_falls_back_to_organization() -> None:
    assert effective_timezone("Africa/Lagos") == "Africa/Lagos"
    assert effective_timezone("Africa/Lagos", "Europe/London") == "Europe/London"
