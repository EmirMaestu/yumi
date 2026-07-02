"""GET /api/splits/summary: 404 en hogar de 1, estados they_owe/you_owe/even."""


def _make_couple(api, my_share=None, their_share=None):
    with api.conn() as c:
        c.execute("UPDATE users SET household_id=100 WHERE id=1")
        c.execute("INSERT INTO users(id, telegram_id, name, username, password_hash, household_id) "
                  "VALUES (2, 222, 'Pareja', 'p', 'x', 100)")
        if their_share:  # yo (1) pagué, a la pareja le toca `their_share` → me debe
            c.execute("INSERT INTO shared_expenses(payer_user_id, other_user_id, amount, currency, other_share, occurred_at) "
                      "VALUES (1, 2, 1000, 'ARS', ?, '2026-07-01')", (their_share,))
        if my_share:  # la pareja (2) pagó, a mí me toca `my_share` → le debo
            c.execute("INSERT INTO shared_expenses(payer_user_id, other_user_id, amount, currency, other_share, occurred_at) "
                      "VALUES (2, 1, 1000, 'ARS', ?, '2026-07-01')", (my_share,))
        c.commit()


def test_404_household_of_one(api):
    assert api.client.get("/api/splits/summary").status_code == 404


def test_they_owe(api):
    _make_couple(api, their_share=500)
    r = api.client.get("/api/splits/summary").json()
    assert r["status"] == "they_owe" and r["amount"] == 500 and r["other_name"] == "Pareja"


def test_you_owe(api):
    _make_couple(api, my_share=300)
    r = api.client.get("/api/splits/summary").json()
    assert r["status"] == "you_owe" and r["amount"] == 300


def test_even(api):
    _make_couple(api, their_share=400, my_share=400)
    r = api.client.get("/api/splits/summary").json()
    assert r["status"] == "even"
