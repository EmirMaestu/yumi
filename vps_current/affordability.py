"""
Veredicto de "¿puedo permitirme X?". Modulo PURO: recibe los saldos por moneda
y un callable value_in_ars(amount, currency)->float inyectado (igual patron que fx.py),
asi la comparacion cross-moneda es explicita y nunca suma ARS+USD a ciegas.
"""


def afford_verdict(amount, currency, balances, budget_remaining, value_in_ars):
    """amount/currency: lo que se quiere gastar.
    balances: {cur: saldo} disponibles. budget_remaining: ARS restantes del
    presupuesto de la categoria (o None). value_in_ars(amount,cur)->float."""
    cost_ars = value_in_ars(float(amount), currency)
    balance_ars = sum(value_in_ars(v, cur) for cur, v in (balances or {}).items())
    leftover = balance_ars - cost_ars
    affordable = leftover >= 0
    budget_ok = None
    budget_overrun = None
    if budget_remaining is not None:
        budget_ok = cost_ars <= budget_remaining
        if not budget_ok:
            budget_overrun = cost_ars - budget_remaining
    return {
        "cost_ars": round(cost_ars, 2),
        "balance_ars": round(balance_ars, 2),
        "leftover_ars": round(leftover, 2),
        "affordable": affordable,
        "budget_ok": budget_ok,
        "budget_overrun": round(budget_overrun, 2) if budget_overrun is not None else None,
    }
