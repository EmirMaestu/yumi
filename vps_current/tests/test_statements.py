"""Resúmenes mensuales inmutables (D10)."""
from datetime import datetime


def test_statement_generates_and_totals(api):
    acc = api.add_account()
    api.add_tx(acc, 100, type="gasto", occurred_at="2020-03-10T12:00")
    api.add_tx(acc, 300, type="ingreso", occurred_at="2020-03-12T12:00")
    api.add_tx(acc, 999, type="gasto", kind="transfer", occurred_at="2020-03-15T12:00")  # excluido
    r = api.client.get("/api/statements/2020/3")
    assert r.status_code == 200
    d = r.json()
    assert d["gasto_total"] == 100
    assert d["ingreso_total"] == 300
    assert d["n_movimientos"] == 2


def test_statement_is_persisted_immutable(api):
    acc = api.add_account()
    api.add_tx(acc, 100, type="gasto", occurred_at="2020-04-10T12:00")
    api.client.get("/api/statements/2020/4")  # genera y persiste
    # nuevo gasto en el mismo mes NO cambia el snapshot ya generado
    api.add_tx(acc, 50, type="gasto", occurred_at="2020-04-15T12:00")
    d = api.client.get("/api/statements/2020/4").json()
    assert d["gasto_total"] == 100


def test_current_month_not_closed_404(api):
    n = datetime.now()
    r = api.client.get(f"/api/statements/{n.year}/{n.month}")
    assert r.status_code == 404


def test_statements_list(api):
    acc = api.add_account()
    api.add_tx(acc, 50, type="gasto", occurred_at="2020-02-05T12:00")
    api.client.get("/api/statements/2020/2")
    lst = api.client.get("/api/statements").json()
    assert any(s["year"] == 2020 and s["month"] == 2 for s in lst)
