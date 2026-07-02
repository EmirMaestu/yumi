"""Contrato de POST /api/transfers: patas vinculadas, KPIs intactos (BF2, D1, D9, D15)."""
from datetime import datetime


def _this_month():
    now = datetime.now()
    return f"{now.year:04d}-{now.month:02d}-10T12:00"


def _mk(api, from_type="banco", to_type="banco"):
    a = api.add_account(name="Origen", type=from_type)
    b = api.add_account(name="Destino", type=to_type)
    return a, b


def test_transfer_ok_links_two_legs(api):
    a, b = _mk(api)
    r = api.client.post("/api/transfers", json={
        "from_account_id": a, "to_account_id": b, "amount": 1000, "occurred_at": _this_month()})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] and data["transfer_group_id"].startswith("tg_")
    assert len(data["tx_ids"]) == 2

    with api.conn() as c:
        rows = c.execute(
            "SELECT account_id, type, amount, kind, transfer_group_id, currency, occurred_at "
            "FROM transactions ORDER BY type").fetchall()
    # pata gasto en origen, pata ingreso en destino
    gasto = next(r for r in rows if r["type"] == "gasto")
    ingreso = next(r for r in rows if r["type"] == "ingreso")
    assert gasto["account_id"] == a and ingreso["account_id"] == b
    assert gasto["kind"] == "transfer" and ingreso["kind"] == "transfer"
    assert gasto["transfer_group_id"] == ingreso["transfer_group_id"]
    assert gasto["amount"] == ingreso["amount"] == 1000
    assert gasto["occurred_at"] == ingreso["occurred_at"]


def test_transfer_to_credit_is_card_payment(api):
    a, b = _mk(api, to_type="credito")
    r = api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": b, "amount": 500})
    assert r.status_code == 200
    with api.conn() as c:
        kinds = [r["kind"] for r in c.execute("SELECT kind FROM transactions").fetchall()]
    assert kinds == ["card_payment", "card_payment"]


def test_transfer_same_account_400(api):
    a, _ = _mk(api)
    r = api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": a, "amount": 100})
    assert r.status_code == 400


def test_transfer_foreign_account_403(api):
    a, _ = _mk(api)
    other = api.add_account(name="Ajena", user_id=2)
    r = api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": other, "amount": 100})
    assert r.status_code == 403


def test_transfer_nonpositive_amount_400(api):
    a, b = _mk(api)
    assert api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": b, "amount": 0}).status_code == 400
    assert api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": b, "amount": -5}).status_code == 400


def test_transfer_does_not_move_kpis(api):
    a, b = _mk(api)
    api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": b, "amount": 1000, "occurred_at": _this_month()})
    kpis = api.client.get("/api/overview2").json()["kpis"]
    assert kpis["gasto_mes"] == 0 and kpis["ingreso_mes"] == 0


def test_transfer_moves_balances(api):
    a, b = _mk(api)
    api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": b, "amount": 1000, "occurred_at": _this_month()})
    with api.conn() as c:
        bal = dict((r["account_id"], r["b"]) for r in c.execute(
            "SELECT account_id, SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS b "
            "FROM transactions GROUP BY account_id").fetchall())
    assert bal[a] == -1000 and bal[b] == 1000


def test_delete_one_leg_deletes_both(api):
    a, b = _mk(api)
    ids = api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": b, "amount": 1000}).json()["tx_ids"]
    r = api.client.delete(f"/api/transactions/{ids[0]}")
    assert r.status_code == 200
    with api.conn() as c:
        n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert n == 0


def test_patch_transfer_leg_rejected(api):
    a, b = _mk(api)
    ids = api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": b, "amount": 1000}).json()["tx_ids"]
    r = api.client.patch(f"/api/transactions/{ids[0]}", json={"amount": 5})
    assert r.status_code == 400
