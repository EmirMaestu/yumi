"""PATCH /api/transactions acepta occurred_at (fecha editable, UX10)."""


def test_patch_changes_occurred_at(api):
    acc = api.add_account()
    tid = api.add_tx(acc, 100, occurred_at="2026-07-15T12:00")

    r = api.client.patch(f"/api/transactions/{tid}", json={"occurred_at": "2026-06-01T12:00"})
    assert r.status_code == 200

    with api.conn() as c:
        row = c.execute("SELECT occurred_at FROM transactions WHERE id=?", (tid,)).fetchone()
    assert row["occurred_at"] == "2026-06-01T12:00"


def test_patch_foreign_tx_forbidden(api):
    # tx de otro usuario → 403 (no se puede cambiar su fecha)
    acc = api.add_account(user_id=2)
    tid = api.add_tx(acc, 100, user_id=2)
    r = api.client.patch(f"/api/transactions/{tid}", json={"occurred_at": "2026-06-01T12:00"})
    assert r.status_code == 403
