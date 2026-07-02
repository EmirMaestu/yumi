"""Trash + restore de transacciones (BF12/UX7)."""
import json


def test_delete_moves_tx_to_trash(api):
    acc = api.add_account()
    tid = api.add_tx(acc, 100, description="Café")
    r = api.client.delete(f"/api/transactions/{tid}")
    assert r.status_code == 200
    assert r.json()["trash_ids"]
    with api.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
        row = c.execute("SELECT entity, original_id, payload FROM trash").fetchone()
    assert row["entity"] == "transaction" and row["original_id"] == tid
    payload = json.loads(row["payload"])
    assert payload["description"] == "Café" and payload["amount"] == 100


def test_restore_reinserts_tx(api):
    acc = api.add_account()
    tid = api.add_tx(acc, 100, description="Café")
    trash_id = api.client.delete(f"/api/transactions/{tid}").json()["trash_ids"][0]
    r = api.client.post(f"/api/transactions/restore/{trash_id}")
    assert r.status_code == 200
    with api.conn() as c:
        row = c.execute("SELECT id, description, amount FROM transactions").fetchone()
        assert row["description"] == "Café" and row["amount"] == 100
        assert c.execute("SELECT COUNT(*) FROM trash").fetchone()[0] == 0


def test_bulk_delete_one_trash_row_per_tx(api):
    acc = api.add_account()
    ids = [api.add_tx(acc, i + 1) for i in range(3)]
    r = api.client.post("/api/transactions/bulk_delete", json={"ids": ids})
    assert r.status_code == 200
    with api.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM trash WHERE entity='transaction'").fetchone()[0] == 3
        assert c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0


def test_restore_transfer_restores_both_legs(api):
    a = api.add_account(name="A")
    b = api.add_account(name="B")
    ids = api.client.post("/api/transfers", json={"from_account_id": a, "to_account_id": b, "amount": 500}).json()["tx_ids"]
    # borrar una pata borra ambas y deja 2 filas de trash
    trash_ids = api.client.delete(f"/api/transactions/{ids[0]}").json()["trash_ids"]
    assert len(trash_ids) == 2
    with api.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
    # restaurar una restaura ambas patas
    api.client.post(f"/api/transactions/restore/{trash_ids[0]}")
    with api.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 2
        assert c.execute("SELECT COUNT(*) FROM trash").fetchone()[0] == 0
