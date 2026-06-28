from compare import period_delta, format_comparison


def test_period_delta_per_currency():
    rows_a = [{"currency": "ARS", "total": 100000.0}, {"currency": "USD", "total": 50.0}]
    rows_b = [{"currency": "ARS", "total": 80000.0}]
    out = period_delta(rows_a, rows_b)
    assert out["ARS"]["a"] == 100000.0
    assert out["ARS"]["b"] == 80000.0
    assert out["ARS"]["delta"] == 20000.0
    assert round(out["ARS"]["pct"], 1) == 25.0  # +25% vs periodo b
    # USD aparece solo en a -> b=0
    assert out["USD"]["a"] == 50.0
    assert out["USD"]["b"] == 0.0
    assert out["USD"]["delta"] == 50.0
    assert out["USD"]["pct"] is None  # division por cero -> None


def test_period_delta_decrease():
    a = [{"currency": "ARS", "total": 60000.0}]
    b = [{"currency": "ARS", "total": 120000.0}]
    out = period_delta(a, b)
    assert out["ARS"]["delta"] == -60000.0
    assert round(out["ARS"]["pct"], 1) == -50.0


def test_period_delta_empty():
    assert period_delta([], []) == {}


def test_format_comparison_text():
    delta = {"ARS": {"a": 100000.0, "b": 80000.0, "delta": 20000.0, "pct": 25.0}}
    txt = format_comparison("este mes", "el mes pasado", delta, "gastos")
    assert "este mes" in txt and "el mes pasado" in txt
    assert "100,000" in txt and "80,000" in txt
    assert "+20,000" in txt
    assert "25.0%" in txt or "+25" in txt


def test_format_comparison_keeps_currencies_separate():
    delta = {
        "ARS": {"a": 100000.0, "b": 80000.0, "delta": 20000.0, "pct": 25.0},
        "USD": {"a": 50.0, "b": 0.0, "delta": 50.0, "pct": None},
    }
    txt = format_comparison("este mes", "el mes pasado", delta, "gastos")
    lines = [ln for ln in txt.split("\n") if ln.strip()]
    ars_line = [ln for ln in lines if "ARS:" in ln]
    usd_line = [ln for ln in lines if "USD:" in ln]
    assert len(ars_line) == 1 and len(usd_line) == 1
    # nunca se mezclan en una sola cifra
    assert "ARS:" not in usd_line[0]
