from conversation import is_followup, merge_followup, fuzzy_keyword


def test_is_followup_detects_y_prefix():
    assert is_followup("¿y de Lisa?")
    assert is_followup("y la semana pasada")
    assert is_followup("y de naranja?")


def test_is_followup_detects_bare_period():
    assert is_followup("la semana pasada")
    assert is_followup("el mes pasado")
    assert is_followup("ayer")


def test_is_followup_rejects_full_sentences():
    assert not is_followup("cuanto gaste en nafta este mes")
    assert not is_followup("pague 5000 con mp en el super")
    # too long to be a continuation
    assert not is_followup("y ademas quiero saber cuanto gaste en comida afuera durante todo el ano pasado con la naranja")


def test_merge_followup_patches_scope_only():
    prev = {"type": "transacciones", "intencion": "total",
            "filters": {"type": "gasto", "period": "mes", "scope": "mine"}}
    out = merge_followup(prev, "y de Lisa?")
    assert out["filters"]["scope"] == "user:Lisa"
    # everything else preserved
    assert out["filters"]["period"] == "mes"
    assert out["filters"]["type"] == "gasto"
    assert out["intencion"] == "total"


def test_merge_followup_patches_period_only():
    prev = {"type": "transacciones", "intencion": "total",
            "filters": {"type": "gasto", "period": "mes", "scope": "mine"}}
    out = merge_followup(prev, "y la semana pasada")
    assert out["filters"]["period"] == "semana_pasada"
    assert out["filters"]["scope"] == "mine"  # untouched


def test_merge_followup_scope_ours():
    prev = {"filters": {"period": "mes", "scope": "mine"}}
    out = merge_followup(prev, "y los dos?")
    assert out["filters"]["scope"] == "ours"


def test_merge_followup_returns_none_when_nothing_recognized():
    prev = {"filters": {"period": "mes"}}
    assert merge_followup(prev, "y entonces que onda") is None


def test_fuzzy_keyword_recovers_typo():
    cand = ["nafta", "Transporte", "comida", "super"]
    assert fuzzy_keyword("naftaa", cand) == "nafta"


def test_fuzzy_keyword_no_match_returns_none():
    assert fuzzy_keyword("xyzqwerty", ["nafta", "comida"]) is None


def test_fuzzy_keyword_empty_inputs():
    assert fuzzy_keyword("", ["nafta"]) is None
    assert fuzzy_keyword("nafta", []) is None
