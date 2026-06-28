import math
import networth


# get_rate fake: cripto=1450, blue=1400, mep=1300 ARS per USD
def fake_rate(t):
    return {"cripto": 1450.0, "blue": 1400.0, "mep": 1300.0}[t]


def test_account_value_ars_same_currency():
    # ARS balance, valued in ARS, is itself regardless of rate_type
    v = networth.account_value_in(100000.0, "ARS", "ARS", "blue", fake_rate)
    assert v == 100000.0


def test_account_value_usd_to_ars_blue():
    # 200 USD valued in ARS at blue (1400)
    v = networth.account_value_in(200.0, "USD", "ARS", "blue", fake_rate)
    assert v == 280000.0


def test_account_value_takenos_uses_manual_when_set():
    # Takenos account: manual rate 1500 wins over cripto 1450
    v = networth.account_value_in(
        100.0, "USD", "ARS", "takenos", fake_rate, takenos_manual=1500.0)
    assert v == 150000.0


def test_account_value_takenos_falls_back_to_cripto():
    v = networth.account_value_in(
        100.0, "USD", "ARS", "takenos", fake_rate, takenos_manual=None)
    assert v == 145000.0  # 100 * cripto(1450)


def test_account_value_ars_to_usd():
    # 145000 ARS valued in USD at cripto -> 100
    v = networth.account_value_in(145000.0, "ARS", "USD", "cripto", fake_rate)
    assert math.isclose(v, 100.0, rel_tol=1e-9)


def test_net_worth_multi_account_two_totals():
    # account 1 (Efectivo, blue): 100000 ARS
    # account 2 (Takenos, takenos->cripto 1450): 200 USD  -> 290000 ARS, +200 USD
    # account 3 (Banco, blue): 50000 ARS
    balances = [
        {"account_id": 1, "currency": "ARS", "balance": 100000.0, "rate_type": "blue"},
        {"account_id": 2, "currency": "USD", "balance": 200.0, "rate_type": "takenos"},
        {"account_id": 3, "currency": "ARS", "balance": 50000.0, "rate_type": "blue"},
    ]
    res = networth.net_worth(balances, fake_rate, takenos_manual=None)
    # total ARS: 100000 + (200*1450=290000) + 50000 = 440000
    assert math.isclose(res["total_ars"], 440000.0, rel_tol=1e-9)
    # total USD: each ARS valued in USD at its own rate_type (blue 1400),
    # USD valued in USD = itself.
    # 100000/1400 + 200 + 50000/1400 = 71.4286 + 200 + 35.7143 = 307.1429
    assert math.isclose(res["total_usd"], 100000/1400 + 200 + 50000/1400, rel_tol=1e-9)


def test_net_worth_negative_balances_subtract():
    # credit card with negative ARS balance reduces net worth
    balances = [
        {"account_id": 1, "currency": "ARS", "balance": 100000.0, "rate_type": "blue"},
        {"account_id": 2, "currency": "ARS", "balance": -30000.0, "rate_type": "blue"},
    ]
    res = networth.net_worth(balances, fake_rate, takenos_manual=None)
    assert math.isclose(res["total_ars"], 70000.0, rel_tol=1e-9)


def test_net_worth_detail_per_account():
    balances = [
        {"account_id": 7, "currency": "USD", "balance": 100.0, "rate_type": "takenos",
         "name": "Takenos", "icon": "🪙"},
    ]
    res = networth.net_worth(balances, fake_rate, takenos_manual=1500.0)
    assert res["detail"] == [{
        "account_id": 7, "name": "Takenos", "icon": "🪙",
        "currency": "USD", "balance": 100.0,
        "value_ars": 150000.0, "rate_type": "takenos",
    }]


def test_net_worth_empty():
    res = networth.net_worth([], fake_rate)
    assert res["total_ars"] == 0.0 and res["total_usd"] == 0.0 and res["detail"] == []


def test_format_delta_up():
    assert networth.format_delta(440000.0, 400000.0) == "📈 +40,000.00 (+10.0%)"


def test_format_delta_down():
    assert networth.format_delta(360000.0, 400000.0) == "📉 -40,000.00 (-10.0%)"


def test_format_delta_no_previous():
    assert networth.format_delta(440000.0, None) == "— (primer snapshot)"


def test_format_delta_flat_from_zero():
    # previous 0 -> avoid div by zero, show absolute only
    assert networth.format_delta(1000.0, 0.0) == "📈 +1,000.00"


# --- Task-spec extensions: preferred_fx_rate input shape, EUR skip+flag, per_account alias ---

def test_account_balances_preferred_fx_rate_shape():
    # Input shaped per task spec: {name, currency, balance, preferred_fx_rate}.
    # None preferred_fx_rate resolves to 'blue'; 'takenos' resolves to cripto/manual.
    balances = [
        {"name": "Efectivo", "currency": "ARS", "balance": 70000.0,
         "preferred_fx_rate": None},
        {"name": "Takenos", "currency": "USD", "balance": 100.0,
         "preferred_fx_rate": "takenos"},
    ]
    res = networth.net_worth(balances, fake_rate, takenos_manual=None)
    # 70000 ARS + 100 USD * cripto(1450) = 70000 + 145000 = 215000
    assert math.isclose(res["total_ars"], 215000.0, rel_tol=1e-9)
    # 70000/1400 (blue) + 100 USD = 50 + 100 = 150
    assert math.isclose(res["total_usd"], 70000/1400 + 100.0, rel_tol=1e-9)
    # rate_type was resolved from preferred_fx_rate
    assert res["detail"][0]["rate_type"] == "blue"
    assert res["detail"][1]["rate_type"] == "takenos"


def test_explicit_rate_type_overrides_preferred():
    # If both keys are present, explicit rate_type wins.
    b = [{"currency": "USD", "balance": 1.0, "rate_type": "mep",
          "preferred_fx_rate": "blue"}]
    res = networth.net_worth(b, fake_rate)
    assert res["detail"][0]["rate_type"] == "mep"
    assert math.isclose(res["total_ars"], 1300.0, rel_tol=1e-9)  # mep rate


def test_net_worth_eur_skipped_and_flagged():
    # EUR is unsupported by fx -> must NOT crash; skipped + flagged, totals exclude it.
    balances = [
        {"account_id": 1, "currency": "ARS", "balance": 100000.0, "rate_type": "blue"},
        {"account_id": 9, "currency": "EUR", "balance": 500.0, "rate_type": "blue",
         "name": "Cuenta EUR"},
        {"account_id": 2, "currency": "USD", "balance": 100.0, "rate_type": "blue"},
    ]
    res = networth.net_worth(balances, fake_rate)
    # Totals exclude EUR entirely.
    assert math.isclose(res["total_ars"], 100000.0 + 100.0 * 1400.0, rel_tol=1e-9)
    assert math.isclose(res["total_usd"], 100000.0 / 1400.0 + 100.0, rel_tol=1e-9)
    # EUR is not in detail/per_account.
    assert all(d["currency"] != "EUR" for d in res["detail"])
    # EUR is flagged in skipped.
    assert len(res["skipped"]) == 1
    sk = res["skipped"][0]
    assert sk["currency"] == "EUR" and sk["account_id"] == 9
    assert sk["reason"] == "unsupported_currency"
    assert sk["balance"] == 500.0


def test_per_account_is_alias_of_detail():
    balances = [
        {"account_id": 1, "currency": "ARS", "balance": 100000.0, "rate_type": "blue"},
    ]
    res = networth.net_worth(balances, fake_rate)
    assert res["per_account"] == res["detail"]
    assert len(res["per_account"]) == 1


def test_multi_currency_kept_separate_not_summed_raw():
    # Sanity: a USD balance and an ARS balance of the SAME numeric value
    # contribute very different amounts to total_ars (proves no raw summing).
    balances = [
        {"currency": "ARS", "balance": 1000.0, "rate_type": "blue"},
        {"currency": "USD", "balance": 1000.0, "rate_type": "blue"},
    ]
    res = networth.net_worth(balances, fake_rate)
    # 1000 ARS + 1000 USD*1400 = 1000 + 1,400,000 = 1,401,000 (NOT 2000)
    assert math.isclose(res["total_ars"], 1000.0 + 1000.0 * 1400.0, rel_tol=1e-9)
    # total_usd: 1000/1400 + 1000 = 1000.7142857...
    assert math.isclose(res["total_usd"], 1000.0 / 1400.0 + 1000.0, rel_tol=1e-9)
