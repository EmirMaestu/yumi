"""
Conversion de divisas (USD <-> ARS) con soporte Takenos.
Modulo PURO: no importa entorno ni red, es testeable offline.
Recibe `get_rate(rate_type) -> float` por inyeccion (en produccion: get_dolar_rate).

Rate "takenos": usa un valor manual (user_settings.takenos_rate) si existe;
si no, cae a la cotizacion 'cripto' de dolarapi (proxy mas cercano a Takenos/USDT).
"""

TAKENOS_RATE_KEY = "takenos_rate"


def resolve_rate_type(account_preferred, default="blue"):
    """rate_type efectivo para una cuenta (accounts.preferred_fx_rate)."""
    return account_preferred or default


def takenos_rate(get_rate, manual_value=None):
    """USD->ARS estilo Takenos: manual si existe, si no 'cripto'."""
    if manual_value:
        return float(manual_value)
    r = get_rate("cripto")
    if r is None:
        raise ValueError("sin cotizacion 'cripto' para Takenos")
    return float(r)


def convert(amount, from_cur, to_cur, get_rate, rate_type="blue", explicit_rate=None, takenos_manual=None):
    """Convierte amount de from_cur a to_cur. Soporta USD<->ARS. Mismo par = sin cambio."""
    amount = float(amount)
    if from_cur == to_cur:
        return amount
    rate = explicit_rate
    if rate is None:
        if rate_type == "takenos":
            rate = takenos_rate(get_rate, takenos_manual)
        else:
            rate = get_rate(rate_type)
    if rate is None:
        raise ValueError(f"sin cotizacion disponible para {rate_type}")
    rate = float(rate)
    if from_cur == "USD" and to_cur == "ARS":
        return amount * rate
    if from_cur == "ARS" and to_cur == "USD":
        return amount / rate
    raise ValueError(f"par no soportado {from_cur}->{to_cur}")


def value_in_ars(amount, currency, get_rate, rate_type="blue", takenos_manual=None):
    """Valor en ARS. ARS pasa directo; USD se convierte. Otras monedas (EUR) -> ValueError (el caller decide)."""
    if currency == "ARS":
        return float(amount)
    return convert(amount, currency, "ARS", get_rate, rate_type, takenos_manual=takenos_manual)


def value_in_usd(amount, currency, get_rate, rate_type="blue", takenos_manual=None):
    """Valor en USD. USD pasa directo; ARS se convierte."""
    if currency == "USD":
        return float(amount)
    return convert(amount, currency, "USD", get_rate, rate_type, takenos_manual=takenos_manual)
