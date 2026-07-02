"""BF10/D8: _next_occurrence preserva el día pedido, clamp solo a fin de mes real."""
import calendar
from datetime import datetime
import crud_v2


def test_day31_no_crash_and_month_end_clamp():
    s = crud_v2._next_occurrence(31)  # antes crasheaba / clampeaba a 28
    d = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    last = calendar.monthrange(d.year, d.month)[1]
    assert d.day == min(31, last)  # 30/31 según el mes, nunca 28 artificial


def test_regular_day_preserved():
    s = crud_v2._next_occurrence(15)
    d = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    assert d.day == 15
