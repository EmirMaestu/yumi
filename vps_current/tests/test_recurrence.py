import pytest
import recurrence


def test_monthly_clamps_to_month_end():
    # day_of_month 31, next month is Feb -> clamp to 28 (2025 not leap)
    assert recurrence.next_occurrence("monthly", "2025-01-31", 31) == "2025-02-28"


def test_monthly_normal():
    assert recurrence.next_occurrence("monthly", "2025-03-15", 15) == "2025-04-15"


def test_monthly_december_wraps_year():
    assert recurrence.next_occurrence("monthly", "2025-12-10", 10) == "2026-01-10"


def test_weekly_adds_7_days():
    assert recurrence.next_occurrence("weekly", "2025-03-15", None) == "2025-03-22"


def test_weekly_crosses_month():
    assert recurrence.next_occurrence("weekly", "2025-03-28", None) == "2025-04-04"


def test_annual_adds_one_year():
    assert recurrence.next_occurrence("annual", "2025-03-15", None) == "2026-03-15"


def test_annual_leap_day_clamps():
    # 2024-02-29 + 1y -> 2025 has no Feb 29 -> clamp to 2025-02-28
    assert recurrence.next_occurrence("annual", "2024-02-29", None) == "2025-02-28"


def test_accepts_iso_with_time():
    assert recurrence.next_occurrence("weekly", "2025-03-15T09:00", None) == "2025-03-22"


def test_unknown_frequency_raises():
    with pytest.raises(ValueError):
        recurrence.next_occurrence("hourly", "2025-03-15", None)


def test_reminder_daily_keeps_time():
    assert recurrence.next_reminder_at("daily", "2025-03-15T09:00") == "2025-03-16T09:00"


def test_reminder_weekly():
    assert recurrence.next_reminder_at("weekly", "2025-03-15T07:30") == "2025-03-22T07:30"


def test_reminder_monthly_clamps():
    assert recurrence.next_reminder_at("monthly", "2025-01-31T20:00") == "2025-02-28T20:00"


def test_reminder_no_time_defaults_0900():
    # remind_at sin hora -> asumimos 09:00 al re-emitir
    assert recurrence.next_reminder_at("daily", "2025-03-15") == "2025-03-16T09:00"


def test_reminder_none_recurrence_returns_none():
    assert recurrence.next_reminder_at(None, "2025-03-15T09:00") is None
    assert recurrence.next_reminder_at("", "2025-03-15T09:00") is None
