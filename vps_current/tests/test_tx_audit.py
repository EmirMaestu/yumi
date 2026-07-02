"""Auditoría visible: PATCH deja updated_at + audit_log; DELETE audita."""


def test_patch_sets_updated_at_and_audits(api):
    acc = api.add_account()
    tid = api.add_tx(acc, 100, description="Café")
    api.client.patch(f"/api/transactions/{tid}", json={"description": "Café con leche"})
    with api.conn() as c:
        row = c.execute("SELECT updated_at FROM transactions WHERE id=?", (tid,)).fetchone()
        assert row["updated_at"] is not None
        log = c.execute("SELECT entity, action FROM audit_log WHERE entity='transaction' AND action='update'").fetchone()
    assert log is not None


def test_delete_audits(api):
    acc = api.add_account()
    tid = api.add_tx(acc, 100)
    api.client.delete(f"/api/transactions/{tid}")
    with api.conn() as c:
        log = c.execute("SELECT 1 FROM audit_log WHERE entity='transaction' AND action='delete'").fetchone()
    assert log is not None
