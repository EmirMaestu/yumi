"""Logica pura de features proactivas (calendario de pagos, resumen mensual,
alertas de dolar, valuacion de ahorro). Sin DB, sin red, sin telegram: todo
entra por parametros para poder testear offline."""
from datetime import date, datetime, timedelta

import fx


def _as_date(s):
    """Acepta 'YYYY-MM-DD' o 'YYYY-MM-DDTHH:MM' y devuelve date."""
    return datetime.fromisoformat(s.split("T")[0]).date()


def upcoming_payments(recurrings, cards_due, today, horizon=30):
    """Merge de recurrentes (next_occurrence) y vencimientos de tarjeta (next_due)
    en una linea de tiempo ordenada, filtrada a [today, today+horizon].

    recurrings: [{id, description, amount, currency, next_occurrence, account_name, user_id}]
    cards_due:  [{account_id, account_name, user_id, next_due,
                  totals:[{currency,total}]}]  # totals = ciclo_cerrado (lo que se paga)
    Devuelve lista de dicts:
      {kind:'recurring'|'card', due_date:'YYYY-MM-DD', days_left:int, label:str,
       user_id:int, ref_id:int, amounts:[{currency,total}]}
    """
    limit = today + timedelta(days=horizon)
    out = []
    for r in recurrings:
        d = _as_date(r["next_occurrence"])
        if d < today or d > limit:
            continue
        out.append({
            "kind": "recurring",
            "due_date": d.isoformat(),
            "days_left": (d - today).days,
            "label": r.get("description") or "recurrente",
            "user_id": r.get("user_id"),
            "ref_id": r["id"],
            "amounts": [{"currency": r.get("currency", "ARS"),
                         "total": float(r["amount"])}],
        })
    for c in cards_due:
        d = _as_date(c["next_due"])
        if d < today or d > limit:
            continue
        # si no hay nada en el ciclo cerrado, no hay nada que pagar -> se omite
        totals = [t for t in (c.get("totals") or []) if t.get("total")]
        if not totals:
            continue
        out.append({
            "kind": "card",
            "due_date": d.isoformat(),
            "days_left": (d - today).days,
            "label": c.get("account_name") or "Tarjeta",
            "user_id": c.get("user_id"),
            "ref_id": c["account_id"],
            "amounts": totals,
        })
    out.sort(key=lambda e: (e["due_date"], e["kind"], e["label"]))
    return out


def _fmt_amounts(amounts):
    return " + ".join(f"{a['total']:,.2f} {a['currency']}" for a in amounts)


def format_calendar(items):
    if not items:
        return "📅 Proximos pagos (30 dias)\n\nNo hay pagos proximos. 🎉"
    lines = ["📅 Proximos pagos (30 dias)", ""]
    for e in items:
        icon = "💳" if e["kind"] == "card" else "🔁"
        when = "hoy" if e["days_left"] == 0 else (
            "mañana" if e["days_left"] == 1 else f"en {e['days_left']} dias")
        lines.append(f"{icon} {e['due_date']} ({when}) — {e['label']}")
        lines.append(f"   {_fmt_amounts(e['amounts'])}")
    return "\n".join(lines)


def due_pushes_for(items, lead_days=(3, 1)):
    """Filtra los items cuyo days_left está en lead_days y arma el texto del push.
    Devuelve [{label, kind, ref_id, user_id, days_left, amounts, text}]."""
    out = []
    for e in items:
        if e["days_left"] not in lead_days:
            continue
        when = "mañana" if e["days_left"] == 1 else f"en {e['days_left']} dias"
        icon = "💳" if e["kind"] == "card" else "🔁"
        out.append({
            "label": e["label"], "kind": e["kind"], "ref_id": e["ref_id"],
            "user_id": e["user_id"], "days_left": e["days_left"],
            "amounts": e["amounts"],
            "text": f"{icon} {when.capitalize()} vence {e['label']}: {_fmt_amounts(e['amounts'])}",
        })
    return out


def should_run_monthly(today):
    """True solo el dia 1 de cada mes (el job corre a diario y se auto-filtra)."""
    return today.day == 1


def last_month_range(today):
    """(primer_dia, ultimo_dia) del mes ANTERIOR a `today`, ISO 'YYYY-MM-DD'."""
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.isoformat(), last_prev.isoformat()


def fx_alert_should_fire(alert, current_rate, today=None):
    """Decide si una fx_alert debe dispararse.
    - 'above': dispara si current_rate >= threshold.
    - 'below': dispara si current_rate <= threshold.
    Anti-spam: no re-dispara si ya disparo HOY (last_fired_at del mismo dia)."""
    if current_rate is None:
        return False
    direction = alert.get("direction")
    threshold = float(alert.get("threshold"))
    crossed = (current_rate >= threshold) if direction == "above" else (current_rate <= threshold)
    if not crossed:
        return False
    last = alert.get("last_fired_at")
    if last and today and last[:10] == today[:10]:
        return False
    return True


def value_savings_usd(balances, get_rate, takenos_manual=None):
    """Suma los balances en USD y los valua en ARS con la cotizacion estilo Takenos
    (manual si existe, si no 'cripto'). Devuelve cual rate se uso para transparencia.

    balances: [{currency, balance}]  (solo se consideran los USD)
    get_rate: fn(rate_type)->float (inyectada; en main.py = get_dolar_rate)
    """
    total_usd = sum(float(b["balance"]) for b in balances if b.get("currency") == "USD")
    rate = fx.takenos_rate(get_rate, takenos_manual)
    source = "takenos (manual)" if takenos_manual else "cripto"
    return {
        "total_usd": total_usd,
        "rate_used": rate,
        "rate_source": source,
        "total_ars": total_usd * rate,
    }
