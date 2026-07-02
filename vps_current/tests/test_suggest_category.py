"""GET /api/categories/suggest devuelve la categoría aprendida (o null)."""
import finance


def test_suggest_returns_learned_category(api):
    cat = api.add_category("Salud")
    kws = finance.learn_keywords("farmacia")
    assert kws  # sanity: hay al menos una keyword
    with api.conn() as c:
        for kw in kws:
            c.execute("INSERT INTO category_learning(user_id, keyword, category_id, count) VALUES (1,?,?,2)", (kw, cat))
        c.commit()
    r = api.client.get("/api/categories/suggest?description=farmacia y algo")
    assert r.status_code == 200
    assert r.json()["category_id"] == cat


def test_suggest_null_when_unknown(api):
    r = api.client.get("/api/categories/suggest?description=xyzqwer")
    assert r.json()["category_id"] is None
