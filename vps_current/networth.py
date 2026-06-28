"""Calculo puro de patrimonio (net worth). Sin DB / red / Telegram: testeable offline.

Recibe los balances por cuenta+moneda y una funcion get_rate inyectada. Cada balance
se valua a la moneda destino ANTES de sumar: NUNCA se suman ARS+USD numericamente.
Las monedas no soportadas por fx (EUR, etc.) se omiten de los totales y se listan
aparte en `skipped` (flag), sin romper el calculo.
"""
import fx


def account_value_in(balance, currency, target, rate_type, get_rate, takenos_manual=None):
    """Valua un balance (de una cuenta, en `currency`) en `target` usando fx.

    rate_type es el preferido de la cuenta ('takenos' resuelve manual-o-cripto).
    Misma moneda devuelve el balance tal cual (sin tocar get_rate).
    """
    if currency == target:
        return float(balance)
    return fx.convert(balance, currency, target, get_rate,
                      rate_type=rate_type, takenos_manual=takenos_manual)


def _rate_type_for(b):
    """rate_type efectivo de un balance. Acepta `rate_type` explicito o,
    si no, lo resuelve desde `preferred_fx_rate` (estilo cuentas)."""
    if b.get("rate_type"):
        return b["rate_type"]
    return fx.resolve_rate_type(b.get("preferred_fx_rate"), default="blue")


def net_worth(account_balances, get_rate, takenos_manual=None):
    """account_balances: lista de dicts por cuenta+moneda. Claves usadas:
      - currency, balance (requeridas)
      - rate_type  o  preferred_fx_rate  (opcional; default 'blue')
      - account_id, name, icon (opcionales, para el detalle)

    Devuelve {total_ars, total_usd, detail, per_account, skipped}.

    total_ars y total_usd se calculan POR SEPARADO desde los mismos balances:
    cada balance se valua a la moneda destino antes de sumar (nunca ARS+USD juntos).
    Monedas no soportadas por fx (EUR, etc.) se OMITEN de los totales y se acumulan
    en `skipped` con un flag, sin romper el total. `per_account` es alias de `detail`.
    """
    total_ars = 0.0
    total_usd = 0.0
    detail = []
    skipped = []
    for b in account_balances:
        cur = b["currency"]
        bal = float(b["balance"])
        rt = _rate_type_for(b)
        try:
            val_ars = account_value_in(bal, cur, "ARS", rt, get_rate, takenos_manual)
            val_usd = account_value_in(bal, cur, "USD", rt, get_rate, takenos_manual)
        except (ValueError, KeyError):
            # Moneda no soportada por fx (EUR, etc.): se lista aparte, no suma a totales.
            skipped.append({
                "account_id": b.get("account_id"),
                "name": b.get("name"),
                "icon": b.get("icon"),
                "currency": cur,
                "balance": bal,
                "rate_type": rt,
                "reason": "unsupported_currency",
            })
            continue
        total_ars += val_ars
        total_usd += val_usd
        detail.append({
            "account_id": b.get("account_id"),
            "name": b.get("name"),
            "icon": b.get("icon"),
            "currency": cur,
            "balance": bal,
            "value_ars": val_ars,
            "rate_type": rt,
        })
    return {
        "total_ars": total_ars,
        "total_usd": total_usd,
        "detail": detail,
        "per_account": detail,
        "skipped": skipped,
    }


def format_delta(current, previous):
    """String de variacion vs snapshot anterior, en la misma moneda que `current`."""
    if previous is None:
        return "— (primer snapshot)"
    diff = current - previous
    arrow = "📈" if diff >= 0 else "📉"
    sign = "+" if diff >= 0 else "-"
    abs_str = f"{abs(diff):,.2f}"
    if previous == 0:
        return f"{arrow} {sign}{abs_str}"
    pct = diff / previous * 100.0
    return f"{arrow} {sign}{abs_str} ({'+' if pct >= 0 else '-'}{abs(pct):.1f}%)"
