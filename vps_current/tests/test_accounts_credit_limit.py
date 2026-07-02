"""accounts.credit_limit: POST lo persiste, GET lo devuelve, PATCH lo actualiza (UX1)."""


def test_create_account_with_credit_limit(api):
    r = api.client.post("/api/accounts", json={"name": "Visa", "type": "credito", "credit_limit": 2000000})
    assert r.status_code == 200
    accs = api.client.get("/api/accounts").json()
    visa = next(a for a in accs if a["name"] == "Visa")
    assert visa["credit_limit"] == 2000000


def test_patch_credit_limit(api):
    aid = api.client.post("/api/accounts", json={"name": "Amex", "type": "credito"}).json()["id"]
    r = api.client.patch(f"/api/accounts/{aid}", json={"credit_limit": 500000})
    assert r.status_code == 200
    accs = api.client.get("/api/accounts").json()
    amex = next(a for a in accs if a["id"] == aid)
    assert amex["credit_limit"] == 500000
