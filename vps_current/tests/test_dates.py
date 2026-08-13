import os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dates


def test_date_only_gets_midnight():
    assert dates.to_isoformat("2026-07-03") == "2026-07-03T00:00"

def test_space_datetime_untouched():
    # el bug: le agregaba T00:00 -> "2026-07-03 21:00:00T00:00" -> ValueError (tumbó el bot)
    assert dates.to_isoformat("2026-07-03 21:00:00") == "2026-07-03 21:00:00"

def test_t_datetime_untouched():
    assert dates.to_isoformat("2026-07-03T21:00") == "2026-07-03T21:00"

def test_whitespace_trimmed():
    assert dates.to_isoformat("  2026-07-03  ") == "2026-07-03T00:00"

def test_none_does_not_raise():
    assert isinstance(dates.to_isoformat(None), str)  # defensivo, no revienta

def test_all_forms_parse_with_fromisoformat():
    # lo que realmente importa: los 3 formatos parsean sin excepción
    for s in ("2026-07-03", "2026-07-03 21:00:00", "2026-07-03T21:00", "2026-12-31 09:30:00"):
        datetime.fromisoformat(dates.to_isoformat(s))  # no debe lanzar
