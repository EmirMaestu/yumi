import trends


def test_month_labels():
    assert trends._month_labels(3, "2026-06-15") == ["2026-04", "2026-05", "2026-06"]
    # cruce de año
    assert trends._month_labels(3, "2026-01-10") == ["2025-11", "2025-12", "2026-01"]


def test_monthly_trend_shape_and_values():
    rows = [
        {"ym": "2026-05", "type": "gasto", "currency": "ARS", "total": 1000},
        {"ym": "2026-06", "type": "gasto", "currency": "ARS", "total": 2000},
        {"ym": "2026-06", "type": "ingreso", "currency": "ARS", "total": 5000},
        {"ym": "2026-06", "type": "gasto", "currency": "USD", "total": 30},
    ]
    out = trends.monthly_trend(rows, months=3, today="2026-06-30")
    assert out["labels"] == ["2026-04", "2026-05", "2026-06"]
    assert out["series"]["gasto"]["ARS"] == [0.0, 1000.0, 2000.0]
    assert out["series"]["ingreso"]["ARS"] == [0.0, 0.0, 5000.0]
    assert out["series"]["gasto"]["USD"] == [0.0, 0.0, 30.0]  # USD separado, no mezclado con ARS


def test_monthly_trend_ignores_out_of_range():
    rows = [{"ym": "2025-01", "type": "gasto", "currency": "ARS", "total": 999}]
    out = trends.monthly_trend(rows, months=2, today="2026-06-30")
    assert out["series"]["gasto"] == {}  # fuera de rango -> ignorado


def test_bucket_by_category_filters_currency():
    rows = [
        {"ym": "2026-06", "cat": "Comida", "currency": "ARS", "total": 1500},
        {"ym": "2026-05", "cat": "Comida", "currency": "ARS", "total": 800},
        {"ym": "2026-06", "cat": "Viajes", "currency": "USD", "total": 200},
    ]
    out = trends.bucket_by_category(rows, months=2, today="2026-06-30", currency="ARS")
    assert out["labels"] == ["2026-05", "2026-06"]
    assert out["series"]["Comida"] == [800.0, 1500.0]
    assert "Viajes" not in out["series"]  # USD filtrado
