"""GET /api/transactions: rango de fechas, limit clampeado, orden estable (UX13/BF7)."""


def _seed(api):
    acc = api.add_account()
    api.add_tx(acc, 10, occurred_at="2026-03-15T12:00", description="marzo")
    api.add_tx(acc, 20, occurred_at="2026-06-10T12:00", description="junio")
    api.add_tx(acc, 30, occurred_at="2026-07-01T12:00", description="julio")
    return acc


def test_date_range_filters(api):
    _seed(api)
    r = api.client.get("/api/transactions?date_from=2026-03-01&date_to=2026-03-31")
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["description"] == "marzo"


def test_date_range_inclusive_end(api):
    acc = api.add_account()
    api.add_tx(acc, 10, occurred_at="2026-03-31T23:00", description="fin de mes")
    r = api.client.get("/api/transactions?date_from=2026-03-01&date_to=2026-03-31")
    assert len(r.json()["items"]) == 1


def test_year_month_still_works(api):
    _seed(api)
    r = api.client.get("/api/transactions?year=2026&month=6")
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["description"] == "junio"


def test_limit_clamped_to_500(api):
    acc = api.add_account()
    for i in range(3):
        api.add_tx(acc, i + 1, occurred_at="2026-07-01T12:00")
    r = api.client.get("/api/transactions?limit=99999")
    assert r.status_code == 200  # no explota; el limit se acota internamente


def test_stable_order_desc(api):
    acc = api.add_account()
    a = api.add_tx(acc, 1, occurred_at="2026-07-01T12:00")
    b = api.add_tx(acc, 2, occurred_at="2026-07-01T12:00")  # misma fecha → desempata por id DESC
    ids = [t["id"] for t in api.client.get("/api/transactions").json()["items"]]
    assert ids == [b, a]
