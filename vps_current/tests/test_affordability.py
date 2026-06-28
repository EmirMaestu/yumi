from affordability import afford_verdict


# value_in_ars: ARS passthrough, USD*1450
def viars(amount, currency):
    return float(amount) if currency == "ARS" else float(amount) * 1450


def test_afford_yes_enough_balance():
    balances = {"ARS": 200000.0}
    v = afford_verdict(50000, "ARS", balances, budget_remaining=None, value_in_ars=viars)
    assert v["affordable"] is True
    assert v["leftover_ars"] == 150000.0
    assert v["budget_ok"] is None


def test_afford_no_insufficient_balance():
    balances = {"ARS": 30000.0}
    v = afford_verdict(50000, "ARS", balances, budget_remaining=None, value_in_ars=viars)
    assert v["affordable"] is False
    assert v["leftover_ars"] == -20000.0


def test_afford_usd_cost_against_ars_balance():
    # quiero gastar 50 USD (=72500 ARS), tengo 100k ARS
    balances = {"ARS": 100000.0}
    v = afford_verdict(50, "USD", balances, budget_remaining=None, value_in_ars=viars)
    assert v["cost_ars"] == 72500.0
    assert v["affordable"] is True
    assert v["leftover_ars"] == 27500.0


def test_afford_multi_currency_balance_summed_in_ars():
    balances = {"ARS": 50000.0, "USD": 40.0}  # 50000 + 58000 = 108000 ARS
    v = afford_verdict(80000, "ARS", balances, budget_remaining=None, value_in_ars=viars)
    assert v["balance_ars"] == 108000.0
    assert v["affordable"] is True


def test_afford_budget_blocks_even_if_balance_ok():
    balances = {"ARS": 500000.0}
    v = afford_verdict(40000, "ARS", balances, budget_remaining=10000.0, value_in_ars=viars)
    assert v["affordable"] is True       # balance alcanza
    assert v["budget_ok"] is False       # pero se pasa del presupuesto
    assert v["budget_overrun"] == 30000.0


def test_afford_exact_balance_is_affordable():
    # leftover == 0 cuenta como alcanzable
    balances = {"ARS": 50000.0}
    v = afford_verdict(50000, "ARS", balances, budget_remaining=None, value_in_ars=viars)
    assert v["affordable"] is True
    assert v["leftover_ars"] == 0.0


def test_afford_budget_ok_within_limit():
    balances = {"ARS": 500000.0}
    v = afford_verdict(8000, "ARS", balances, budget_remaining=10000.0, value_in_ars=viars)
    assert v["budget_ok"] is True
    assert v["budget_overrun"] is None
