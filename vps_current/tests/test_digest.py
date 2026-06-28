from digest import digest_facts, digest_fallback


def viars(amount, currency):
    return float(amount) if currency == "ARS" else float(amount) * 1450


def test_digest_facts_top_categories_and_total():
    agg = [
        {"category": "Comida", "currency": "ARS", "total": 120000.0, "n": 12},
        {"category": "Transporte", "currency": "ARS", "total": 40000.0, "n": 5},
        {"category": "Suscripciones", "currency": "USD", "total": 20.0, "n": 2},
    ]
    prev = [{"category": "Comida", "currency": "ARS", "total": 60000.0, "n": 8}]
    f = digest_facts(agg, prev, viars)
    # total semana en ARS = 120000 + 40000 + 20*1450 = 189000
    assert f["total_ars"] == 189000.0
    assert f["prev_total_ars"] == 60000.0
    assert f["top"][0]["category"] == "Comida"
    assert f["top"][0]["total_ars"] == 120000.0
    # comida subio 100% vs semana previa -> anomalia
    anomalies = [a for a in f["anomalies"] if a["category"] == "Comida"]
    assert anomalies and anomalies[0]["pct"] == 100.0


def test_digest_facts_empty():
    f = digest_facts([], [], viars)
    assert f["total_ars"] == 0.0
    assert f["top"] == []
    assert f["anomalies"] == []


def test_digest_facts_top_capped_at_three():
    agg = [
        {"category": "A", "currency": "ARS", "total": 5.0, "n": 1},
        {"category": "B", "currency": "ARS", "total": 4.0, "n": 1},
        {"category": "C", "currency": "ARS", "total": 3.0, "n": 1},
        {"category": "D", "currency": "ARS", "total": 2.0, "n": 1},
    ]
    f = digest_facts(agg, [], viars)
    assert len(f["top"]) == 3
    assert [t["category"] for t in f["top"]] == ["A", "B", "C"]


def test_digest_facts_usd_kept_separate_until_converted():
    # misma categoria en dos monedas se acumula en ARS via value_in_ars
    agg = [
        {"category": "Viajes", "currency": "ARS", "total": 10000.0, "n": 1},
        {"category": "Viajes", "currency": "USD", "total": 10.0, "n": 1},
    ]
    f = digest_facts(agg, [], viars)
    # 10000 + 10*1450 = 24500
    assert f["top"][0]["category"] == "Viajes"
    assert f["top"][0]["total_ars"] == 24500.0
    assert f["total_ars"] == 24500.0


def test_digest_fallback_mentions_top_category():
    f = digest_facts(
        [{"category": "Comida", "currency": "ARS", "total": 120000.0, "n": 12}], [], viars)
    txt = digest_fallback(f)
    assert "Comida" in txt
    assert "120,000" in txt or "120000" in txt


def test_digest_fallback_empty():
    f = digest_facts([], [], viars)
    txt = digest_fallback(f)
    assert "no registraste gastos" in txt
