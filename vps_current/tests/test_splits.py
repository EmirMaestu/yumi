import splits


# --- default_share -----------------------------------------------------------

def test_default_share_half_by_default():
    assert splits.default_share(80000.0, None) == 40000.0
    assert splits.default_share(100.0, None) == 50.0


def test_default_share_explicit_value_wins():
    assert splits.default_share(80000.0, 30000.0) == 30000.0


def test_default_share_clamped_to_total():
    # nunca puede deber mas que el total
    assert splits.default_share(100.0, 250.0) == 100.0


def test_default_share_negative_floored_to_zero():
    assert splits.default_share(100.0, -10.0) == 0.0


# --- split_shares (my_share, their_share) ------------------------------------

def test_split_shares_half_by_default():
    assert splits.split_shares(80000.0) == (40000.0, 40000.0)
    assert splits.split_shares(100.0, None) == (50.0, 50.0)


def test_split_shares_explicit_other_share():
    # other_share=30000 sobre 80000 => yo pongo 50000
    assert splits.split_shares(80000.0, 30000.0) == (50000.0, 30000.0)


def test_split_shares_clamped():
    # other_share mayor que el total => el otro pone todo, yo 0
    assert splits.split_shares(100.0, 250.0) == (0.0, 100.0)


def test_split_shares_sum_equals_total():
    my, their = splits.split_shares(99.99)
    assert round(my + their, 2) == 99.99


# --- net_balance -------------------------------------------------------------

def _row(payer, other, share, cur="ARS", settled=None):
    return {"payer_user_id": payer, "other_user_id": other,
            "other_share": share, "currency": cur, "settled_at": settled}


def test_net_balance_other_owes_me():
    # yo (1) pague, a Lisa (2) le toca 40000 -> Lisa me debe 40000
    rows = [_row(1, 2, 40000.0)]
    assert splits.net_balance(rows, 1, 2) == {"ARS": 40000.0}


def test_net_balance_i_owe_other():
    # Lisa (2) pago, a mi (1) me toca 40000 -> yo le debo 40000 (negativo)
    rows = [_row(2, 1, 40000.0)]
    assert splits.net_balance(rows, 1, 2) == {"ARS": -40000.0}


def test_net_balance_nets_out_per_currency():
    rows = [
        _row(1, 2, 40000.0, "ARS"),   # Lisa me debe 40k
        _row(2, 1, 15000.0, "ARS"),   # yo le debo 15k
        _row(1, 2, 30.0, "USD"),      # Lisa me debe 30 usd
    ]
    assert splits.net_balance(rows, 1, 2) == {"ARS": 25000.0, "USD": 30.0}


def test_net_balance_ignores_settled():
    rows = [
        _row(1, 2, 40000.0, "ARS", settled="2026-06-01T10:00"),
        _row(1, 2, 5000.0, "ARS"),
    ]
    assert splits.net_balance(rows, 1, 2) == {"ARS": 5000.0}


def test_net_balance_ignores_unrelated_users():
    rows = [_row(1, 3, 40000.0), _row(2, 1, 10000.0)]
    # solo cuenta el split entre 1 y 2
    assert splits.net_balance(rows, 1, 2) == {"ARS": -10000.0}


def test_net_balance_drops_zero_nets():
    rows = [_row(1, 2, 20000.0), _row(2, 1, 20000.0)]
    assert splits.net_balance(rows, 1, 2) == {}


def test_net_balance_empty_rows():
    assert splits.net_balance([], 1, 2) == {}


def test_net_balance_default_currency_when_missing():
    rows = [{"payer_user_id": 1, "other_user_id": 2, "other_share": 100.0,
             "currency": None, "settled_at": None}]
    assert splits.net_balance(rows, 1, 2) == {"ARS": 100.0}


# --- format_balance ----------------------------------------------------------

def test_format_balance_other_owes_me():
    out = splits.format_balance({"ARS": 40000.0}, "Emir", "Lisa")
    assert "Lisa te debe" in out
    assert "$40.000,00" in out


def test_format_balance_i_owe_other():
    out = splits.format_balance({"ARS": -15000.0}, "Emir", "Lisa")
    assert "Le debes a Lisa" in out
    assert "$15.000,00" in out


def test_format_balance_usd_symbol():
    out = splits.format_balance({"USD": 30.0}, "Emir", "Lisa")
    assert "Lisa te debe" in out
    assert "US$30,00" in out


def test_format_balance_multi_currency_two_lines():
    out = splits.format_balance({"ARS": 25000.0, "USD": -10.0}, "Emir", "Lisa")
    assert "Lisa te debe" in out
    assert "Le debes a Lisa" in out
    assert out.count("\n") >= 1


def test_format_balance_settled():
    assert splits.format_balance({}, "Emir", "Lisa") == "Estan a mano \U0001F91D"


# --- summarize_settlement ----------------------------------------------------

def test_summarize_settlement_counts_only_unsettled_pair():
    rows = [
        _row(1, 2, 40000.0, "ARS"),
        _row(2, 1, 15000.0, "ARS"),
        _row(1, 2, 5000.0, "ARS", settled="2026-01-01T00:00"),  # ya saldado
        _row(1, 3, 9999.0, "ARS"),                              # otro usuario
    ]
    s = splits.summarize_settlement(rows, 1, 2)
    assert s["count"] == 2
    assert s["balance"] == {"ARS": 25000.0}


def test_summarize_settlement_empty():
    s = splits.summarize_settlement([], 1, 2)
    assert s["count"] == 0
    assert s["balance"] == {}


# --- settle_summary (one-line) -----------------------------------------------

def test_settle_summary_empty():
    assert splits.settle_summary({}) == "Estan a mano \U0001F91D"


def test_settle_summary_other_owes_me():
    out = splits.settle_summary({"ARS": 40000.0})
    assert "te deben" in out
    assert "$40.000,00" in out


def test_settle_summary_i_owe():
    out = splits.settle_summary({"ARS": -15000.0})
    assert "debes" in out
    assert "$15.000,00" in out


def test_settle_summary_multi_currency():
    out = splits.settle_summary({"ARS": 25000.0, "USD": -10.0})
    assert "te deben $25.000,00" in out
    assert "debes US$10,00" in out
    assert ";" in out
