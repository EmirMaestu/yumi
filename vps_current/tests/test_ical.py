import ical


def test_ics_escape():
    assert ical.ics_escape("a,b;c\\d") == "a\\,b\\;c\\\\d"
    assert ical.ics_escape("line1\nline2") == "line1\\nline2"


def test_ics_dt_naive_local():
    # 'YYYY-MM-DDTHH:MM' -> 'YYYYMMDDTHHMMSS' (hora local, sin Z)
    assert ical.ics_dt("2025-03-15T09:30") == "20250315T093000"


def test_ics_dt_date_only_midnight():
    assert ical.ics_dt("2025-03-15") == "20250315T000000"


def test_fold_line_short_unchanged():
    assert ical.fold_line("SUMMARY:hola") == "SUMMARY:hola"


def test_fold_line_long_folds_at_75():
    long = "SUMMARY:" + "x" * 100
    folded = ical.fold_line(long)
    parts = folded.split("\r\n")
    assert len(parts) > 1
    assert all(len(p.encode("utf-8")) <= 75 for p in parts)
    # las continuaciones empiezan con espacio
    assert all(p.startswith(" ") for p in parts[1:])


def test_build_ics_minimal():
    events = [
        {"uid": "ev-1@asistente", "summary": "Cena con Ana", "start": "2025-03-15T21:00",
         "location": "Palermo", "description": ""},
    ]
    out = ical.build_ics(events, calname="Asistente")
    assert out.startswith("BEGIN:VCALENDAR\r\n")
    assert out.rstrip().endswith("END:VCALENDAR")
    assert "VERSION:2.0" in out
    assert "X-WR-CALNAME:Asistente" in out
    assert "BEGIN:VEVENT\r\n" in out
    assert "UID:ev-1@asistente" in out
    assert "SUMMARY:Cena con Ana" in out
    assert "DTSTART:20250315T210000" in out
    assert "LOCATION:Palermo" in out
    assert "END:VEVENT\r\n" in out


def test_build_ics_escapes_summary():
    events = [{"uid": "x@a", "summary": "Pago; luz, gas", "start": "2025-03-15T09:00",
               "location": "", "description": ""}]
    out = ical.build_ics(events, calname="X")
    assert "SUMMARY:Pago\\; luz\\, gas" in out
