"""CRUD de metas de ahorro con propiedad estricta."""


def test_savings_crud(api):
    gid = api.client.post("/api/savings_goals", json={"name": "Viaje", "target_amount": 1000, "currency": "USD"}).json()["id"]
    lst = api.client.get("/api/savings_goals").json()
    assert any(g["id"] == gid and g["name"] == "Viaje" for g in lst)
    # aporte manual
    api.client.patch(f"/api/savings_goals/{gid}", json={"current_amount": 250})
    g = next(g for g in api.client.get("/api/savings_goals").json() if g["id"] == gid)
    assert g["current_amount"] == 250
    # borrar
    api.client.delete(f"/api/savings_goals/{gid}")
    assert not any(g["id"] == gid for g in api.client.get("/api/savings_goals").json())


def test_savings_target_must_be_positive(api):
    assert api.client.post("/api/savings_goals", json={"name": "X", "target_amount": 0}).status_code == 400


def test_savings_foreign_forbidden(api):
    with api.conn() as c:
        c.execute("INSERT INTO savings_goals(id, user_id, name, target_amount) VALUES (99, 2, 'ajena', 100)")
        c.commit()
    assert api.client.patch("/api/savings_goals/99", json={"current_amount": 5}).status_code == 403
    assert api.client.delete("/api/savings_goals/99").status_code == 403
