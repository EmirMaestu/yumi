"""Tests de API para transactions.kind: KPIs por kind (BF3/C2) y whitelist del POST."""
from datetime import datetime


def _this_month_day15():
    now = datetime.now()
    return f"{now.year:04d}-{now.month:02d}-15T12:00"


# ── Task 12: overview2 KPIs suman solo kind='normal' ────────────────────────
def test_overview2_gasto_mes_excludes_adjustment_and_transfer(api):
    acc = api.add_account()
    when = _this_month_day15()
    api.add_tx(acc, 100, type="gasto", kind="normal", occurred_at=when)
    api.add_tx(acc, 500, type="gasto", kind="adjustment", occurred_at=when)
    api.add_tx(acc, 200, type="gasto", kind="transfer", occurred_at=when)

    r = api.client.get("/api/overview2")
    assert r.status_code == 200
    assert r.json()["kpis"]["gasto_mes"] == 100


def test_overview2_ingreso_mes_excludes_non_normal(api):
    acc = api.add_account()
    when = _this_month_day15()
    api.add_tx(acc, 300, type="ingreso", kind="normal", occurred_at=when)
    api.add_tx(acc, 999, type="ingreso", kind="transfer", occurred_at=when)

    r = api.client.get("/api/overview2")
    assert r.json()["kpis"]["ingreso_mes"] == 300


# ── Task 13: POST /api/transactions acepta kind con whitelist ───────────────
def test_post_tx_accepts_adjustment_kind(api):
    acc = api.add_account()
    r = api.client.post("/api/transactions", json={
        "type": "gasto", "amount": 500, "account_id": acc,
        "occurred_at": _this_month_day15(), "kind": "adjustment"})
    assert r.status_code == 200
    with api.conn() as c:
        row = c.execute("SELECT kind FROM transactions WHERE id=?", (r.json()["id"],)).fetchone()
    assert row["kind"] == "adjustment"


def test_post_tx_defaults_to_normal_kind(api):
    acc = api.add_account()
    r = api.client.post("/api/transactions", json={
        "type": "gasto", "amount": 100, "account_id": acc, "occurred_at": _this_month_day15()})
    assert r.status_code == 200
    with api.conn() as c:
        row = c.execute("SELECT kind FROM transactions WHERE id=?", (r.json()["id"],)).fetchone()
    assert row["kind"] == "normal"


def test_post_tx_rejects_transfer_kind(api):
    acc = api.add_account()
    r = api.client.post("/api/transactions", json={
        "type": "gasto", "amount": 100, "account_id": acc,
        "occurred_at": _this_month_day15(), "kind": "transfer"})
    assert r.status_code == 400
