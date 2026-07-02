"""overview2: proyección de fin de mes + anomalías (finance.py)."""
from datetime import datetime


def _this_month_day(d=10):
    n = datetime.now()
    return f"{n.year:04d}-{n.month:02d}-{d:02d}T12:00"


def _months_ago(k):
    n = datetime.now()
    y, m = n.year, n.month - k
    while m <= 0:
        m += 12; y -= 1
    return f"{y:04d}-{m:02d}-10T12:00"


def test_proyeccion_present_and_extrapolates(api):
    acc = api.add_account()
    api.add_tx(acc, 1000, type="gasto", occurred_at=_this_month_day(5))
    k = api.client.get("/api/overview2").json()["kpis"]
    assert "proyeccion_fin_mes" in k
    # la proyección nunca es menor al gasto acumulado
    assert k["proyeccion_fin_mes"] >= k["gasto_mes"]


def test_anomalia_detecta_gasto_atipico(api):
    acc = api.add_account()
    cat = api.add_category("Súper")
    # histórico reciente (meses anteriores, dentro de la ventana): 5 gastos chicos
    for i in range(1, 6):
        api.add_tx(acc, 1000, type="gasto", category_id=cat, occurred_at=_months_ago(i))
    # este mes: un gasto enorme en la misma categoría
    api.add_tx(acc, 500000, type="gasto", category_id=cat, occurred_at=_this_month_day(8))
    anomalias = api.client.get("/api/overview2").json()["kpis"]["anomalias"]
    assert any(a["amount"] == 500000 for a in anomalias)


def test_no_anomalia_sin_historico(api):
    acc = api.add_account()
    cat = api.add_category("Nueva")
    api.add_tx(acc, 999999, type="gasto", category_id=cat, occurred_at=_this_month_day(8))
    anomalias = api.client.get("/api/overview2").json()["kpis"]["anomalias"]
    assert anomalias == []  # sin >=4 puntos históricos, no dispara
