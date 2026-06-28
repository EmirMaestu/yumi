import proactive


def _get_rate(t):
    return {"cripto": 1450.0, "blue": 1400.0, "oficial": 1000.0}[t]


def test_value_savings_usd_takenos_manual_wins():
    # 1000 USD + 500 USD = 1500 USD; rate takenos manual 1480
    balances = [{"currency": "USD", "balance": 1000.0},
                {"currency": "USD", "balance": 500.0}]
    res = proactive.value_savings_usd(balances, _get_rate, takenos_manual=1480.0)
    assert res["total_usd"] == 1500.0
    assert res["total_ars"] == 1500.0 * 1480.0
    assert res["rate_used"] == 1480.0
    assert res["rate_source"] == "takenos (manual)"


def test_value_savings_usd_falls_back_to_cripto():
    balances = [{"currency": "USD", "balance": 200.0}]
    res = proactive.value_savings_usd(balances, _get_rate, takenos_manual=None)
    assert res["total_usd"] == 200.0
    assert res["total_ars"] == 200.0 * 1450.0
    assert res["rate_used"] == 1450.0
    assert res["rate_source"] == "cripto"


def test_value_savings_usd_ignores_non_usd():
    balances = [{"currency": "USD", "balance": 100.0},
                {"currency": "ARS", "balance": 999999.0}]
    res = proactive.value_savings_usd(balances, _get_rate, takenos_manual=None)
    assert res["total_usd"] == 100.0
    # el balance ARS no contamina el total valuado
    assert res["total_ars"] == 100.0 * 1450.0


def test_value_savings_usd_empty_balances():
    res = proactive.value_savings_usd([], _get_rate, takenos_manual=None)
    assert res["total_usd"] == 0
    assert res["total_ars"] == 0
    assert res["rate_source"] == "cripto"
