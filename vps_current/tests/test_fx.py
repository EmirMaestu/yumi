import pytest
import fx

FAKE = {"cripto": 1450.0, "blue": 1400.0, "oficial": 1000.0, "mep": 1380.0}


def get_rate(t):
    return FAKE[t]


def test_same_currency_passthrough():
    assert fx.convert(100, "ARS", "ARS", get_rate) == 100.0
    assert fx.convert(50, "USD", "USD", get_rate) == 50.0


def test_usd_to_ars_blue():
    assert fx.convert(10, "USD", "ARS", get_rate, rate_type="blue") == 14000.0


def test_ars_to_usd_blue():
    assert fx.convert(14000, "ARS", "USD", get_rate, rate_type="blue") == 10.0


def test_takenos_uses_cripto_when_no_manual():
    assert fx.convert(10, "USD", "ARS", get_rate, rate_type="takenos") == 14500.0


def test_takenos_manual_overrides_cripto():
    assert fx.convert(10, "USD", "ARS", get_rate, rate_type="takenos", takenos_manual=1500) == 15000.0


def test_explicit_rate_wins():
    assert fx.convert(10, "USD", "ARS", get_rate, rate_type="blue", explicit_rate=2000) == 20000.0


def test_unsupported_pair_raises():
    with pytest.raises(ValueError):
        fx.convert(10, "EUR", "ARS", get_rate)


def test_none_rate_raises_valueerror():
    # get_rate devuelve None (ej. dolarapi caido) -> ValueError, NO TypeError
    none_rate = lambda t: None
    with pytest.raises(ValueError):
        fx.convert(10, "USD", "ARS", none_rate, rate_type="blue")
    with pytest.raises(ValueError):
        fx.convert(10, "USD", "ARS", none_rate, rate_type="takenos")


def test_value_in_ars():
    assert fx.value_in_ars(100, "ARS", get_rate) == 100.0
    assert fx.value_in_ars(10, "USD", get_rate, rate_type="takenos") == 14500.0


def test_value_in_usd():
    assert fx.value_in_usd(50, "USD", get_rate) == 50.0
    assert fx.value_in_usd(14500, "ARS", get_rate, rate_type="takenos") == 10.0


def test_resolve_rate_type():
    assert fx.resolve_rate_type(None) == "blue"
    assert fx.resolve_rate_type("takenos") == "takenos"


def test_takenos_rate_helper():
    assert fx.takenos_rate(get_rate) == 1450.0
    assert fx.takenos_rate(get_rate, 1600) == 1600.0
