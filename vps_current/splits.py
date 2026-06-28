# splits.py — logica pura de gastos compartidos (Splitwise de la pareja).
# SIN imports de env/DB/Telegram/red: 100% testeable offline.
#
# Convencion de datos: un split (fila de shared_expenses) es un dict con al menos
#   payer_user_id, other_user_id, amount (total), other_share (lo que le toca al OTRO),
#   currency, settled_at.
# El que paga adelanto `other_share` por el otro => el otro le debe `other_share`.
# net_balance: positivo => el otro me debe; negativo => yo le debo.
# Nunca se mezclan monedas distintas en una sola cifra: el balance es por moneda.


def default_share(amount, other_share=None):
    """Cuanto le corresponde al OTRO del total `amount`.
    Default: la mitad. Si viene `other_share` explicito, se respeta,
    clamp a [0, amount]."""
    amount = float(amount)
    if other_share is None:
        return round(amount / 2.0, 2)
    s = float(other_share)
    if s < 0:
        return 0.0
    if s > amount:
        return amount
    return round(s, 2)


def split_shares(amount, other_share=None):
    """Reparte `amount` entre yo y el otro. Devuelve (my_share, their_share).
    Por defecto mitad y mitad; si viene other_share explicito se respeta
    (clampeado a [0, amount]) y my_share es el resto."""
    amount = float(amount)
    their_share = default_share(amount, other_share)
    my_share = round(amount - their_share, 2)
    return (my_share, their_share)


def net_balance(rows, me_id, other_id):
    """Neto por moneda entre me_id y other_id sobre splits SIN saldar.
    Positivo => el otro me debe; negativo => yo le debo. Omite netos 0."""
    bal = {}
    pair = {me_id, other_id}
    for r in rows:
        if r.get("settled_at"):
            continue
        payer = r["payer_user_id"]
        other = r["other_user_id"]
        if {payer, other} != pair:
            continue
        cur = r.get("currency") or "ARS"
        share = float(r["other_share"])
        if payer == me_id:
            bal[cur] = round(bal.get(cur, 0.0) + share, 2)
        else:  # payer == other_id, el otro pago y a mi me toca share
            bal[cur] = round(bal.get(cur, 0.0) - share, 2)
    return {c: v for c, v in bal.items() if v != 0.0}


_SYMBOL = {"ARS": "$", "USD": "US$", "EUR": "€"}


def _money(amount, currency):
    sym = _SYMBOL.get(currency, currency + " ")
    s = f"{abs(float(amount)):,.2f}"          # 40,000.00  (estilo US)
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # -> 40.000,00
    return f"{sym}{s}"


def format_balance(balance, me_name, other_name):
    """Texto humano del balance. balance: {cur: neto} de net_balance.
    Vacio => 'Estan a mano'."""
    if not balance:
        return "Estan a mano \U0001F91D"
    lines = []
    for cur in sorted(balance):
        neto = balance[cur]
        money = _money(neto, cur)
        if neto > 0:
            lines.append(f"\U0001F7E2 {other_name} te debe {money}")
        else:
            lines.append(f"\U0001F534 Le debes a {other_name} {money}")
    return "\n".join(lines)


def summarize_settlement(rows, me_id, other_id):
    """Para el flujo saldar: cuantos splits no saldados involucran a la pareja
    y cual es el neto resultante por moneda."""
    pair = {me_id, other_id}
    count = sum(
        1 for r in rows
        if not r.get("settled_at") and {r["payer_user_id"], r["other_user_id"]} == pair
    )
    return {"count": count, "balance": net_balance(rows, me_id, other_id)}


def settle_summary(balance):
    """Resumen de una sola linea del balance (lo que devuelve net_balance),
    pensado para confirmaciones cortas. Vacio => estan a mano."""
    if not balance:
        return "Estan a mano \U0001F91D"
    parts = []
    for cur in sorted(balance):
        neto = balance[cur]
        money = _money(neto, cur)
        if neto > 0:
            parts.append(f"te deben {money}")
        else:
            parts.append(f"debes {money}")
    return "; ".join(parts)
