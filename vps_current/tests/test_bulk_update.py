"""bulk_update recategoriza en lote con validación de propiedad (UX15)."""


def test_bulk_update_category(api):
    acc = api.add_account()
    cat = api.add_category("Nueva")
    ids = [api.add_tx(acc, i + 1) for i in range(3)]
    r = api.client.post("/api/transactions/bulk_update", json={"ids": ids, "category_id": cat})
    assert r.status_code == 200
    with api.conn() as c:
        cats = [row["category_id"] for row in c.execute("SELECT category_id FROM transactions").fetchall()]
    assert cats == [cat, cat, cat]


def test_bulk_update_foreign_tx_forbidden(api):
    acc = api.add_account(user_id=2)
    cat = api.add_category("X")
    ids = [api.add_tx(acc, 1, user_id=2)]
    r = api.client.post("/api/transactions/bulk_update", json={"ids": ids, "category_id": cat})
    assert r.status_code == 403
