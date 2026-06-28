import datetime
import streaks


def test_current_streak_includes_today():
    today = datetime.date(2025, 3, 15)
    dates = ["2025-03-15", "2025-03-14", "2025-03-13"]
    assert streaks.current_streak(dates, today) == 3


def test_current_streak_counts_from_yesterday_if_no_today():
    # si no hizo hoy pero hizo ayer y antes, la racha sigue viva (cuenta hasta ayer)
    today = datetime.date(2025, 3, 15)
    dates = ["2025-03-14", "2025-03-13"]
    assert streaks.current_streak(dates, today) == 2


def test_current_streak_broken_returns_zero():
    today = datetime.date(2025, 3, 15)
    dates = ["2025-03-12", "2025-03-11"]  # gap of 2 days
    assert streaks.current_streak(dates, today) == 0


def test_current_streak_dedupes_same_day():
    today = datetime.date(2025, 3, 15)
    dates = ["2025-03-15", "2025-03-15", "2025-03-14"]
    assert streaks.current_streak(dates, today) == 2


def test_current_streak_empty():
    assert streaks.current_streak([], datetime.date(2025, 3, 15)) == 0


def test_current_streak_accepts_datetime_strings():
    today = datetime.date(2025, 3, 15)
    dates = ["2025-03-15 08:00:00", "2025-03-14T22:10"]
    assert streaks.current_streak(dates, today) == 2


def test_weekly_progress():
    # 4 logs esta semana, meta 5 -> (4, 5, 80)
    assert streaks.weekly_progress(4, 5) == (4, 5, 80)


def test_weekly_progress_capped_at_100():
    assert streaks.weekly_progress(7, 5) == (7, 5, 100)


def test_weekly_progress_no_goal():
    assert streaks.weekly_progress(3, None) == (3, None, None)
    assert streaks.weekly_progress(3, 0) == (3, 0, None)


def test_sparkline_7_boxes():
    # presencia por dia: lunes..domingo
    flags = [True, False, True, True, False, False, True]
    assert streaks.sparkline(flags) == "\U0001F7E9⬜\U0001F7E9\U0001F7E9⬜⬜\U0001F7E9"


def test_sparkline_pads_to_7():
    assert streaks.sparkline([True, True]) == "⬜⬜⬜⬜⬜\U0001F7E9\U0001F7E9"
