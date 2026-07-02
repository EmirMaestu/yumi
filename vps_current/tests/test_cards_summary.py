"""/api/cards/summary reproduce la matemática de cards.ts (D2)."""


def _rec(api, account_id, amount, total, fired, active=1):
    with api.conn() as c:
        c.execute("INSERT INTO recurring(account_id, amount, currency, description, next_occurrence, "
                  "total_installments, installments_fired, active, user_id) VALUES (?,?,?,?,?,?,?,?,1)",
                  (account_id, amount, 'ARS', 'plan', '2026-07-01', total, fired, active))
        c.commit()


def test_cards_summary_matches_oracle(api):
    card = api.add_account(name="Visa", type="credito", closing_day=12, due_day=20)
    api.add_tx(card, 100000, type="gasto", occurred_at="2026-07-05T12:00")  # consumos
    _rec(api, card, 20000, 6, 2, active=1)   # activo: 20000×4=80000, cuota mensual 20000
    _rec(api, card, 10000, 4, 1, active=0)   # pausado: 10000×3=30000 (deuda sí, mensual no)

    s = api.client.get("/api/cards/summary").json()
    assert len(s) == 1
    v = s[0]
    assert v["consumos"] == 100000
    assert v["en_cuotas"] == 80000 + 30000       # incluye pausada
    assert v["deuda_total"] == 210000
    assert v["cuotas_mes"] == 20000              # solo el activo
    assert v["credit_limit"] is None


def test_cards_summary_disponible_with_limit(api):
    card = api.add_account(name="Amex", type="credito", closing_day=12, due_day=20)
    with api.conn() as c:
        c.execute("UPDATE accounts SET credit_limit=500000 WHERE id=?", (card,)); c.commit()
    api.add_tx(card, 100000, type="gasto", occurred_at="2026-07-05T12:00")
    v = api.client.get("/api/cards/summary").json()[0]
    assert v["credit_limit"] == 500000
    assert v["disponible"] == 400000  # 500000 - deuda 100000
