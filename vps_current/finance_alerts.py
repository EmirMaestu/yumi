"""Alertas de finanzas (cierre/vencimiento de tarjeta, presupuesto) con dedup.

Funciones puras sobre una conexión sqlite: calculan qué alertas corresponden hoy
y NO fueron enviadas todavía (tabla notifications_sent, UNIQUE(user_id, kind, ref)).
El envío real (push/Telegram) lo hace el job del bot; acá está la lógica testeable.
"""
from datetime import date, timedelta
import vencimientos


def already_sent(conn, user_id, kind, ref):
    return conn.execute(
        "SELECT 1 FROM notifications_sent WHERE user_id=? AND kind=? AND ref=?",
        (user_id, kind, ref)).fetchone() is not None


def mark_sent(conn, user_id, kind, ref):
    conn.execute(
        "INSERT OR IGNORE INTO notifications_sent(user_id, kind, ref, sent_at) "
        "VALUES (?,?,?,datetime('now'))", (user_id, kind, ref))


def _sum_card(conn, account_id, since_iso, until_iso=None):
    q = ("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE account_id=? "
         "AND type='gasto' AND currency='ARS' AND kind='normal' AND occurred_at>?")
    params = [account_id, since_iso]
    if until_iso:
        q += " AND occurred_at<=?"; params.append(until_iso)
    return conn.execute(q, params).fetchone()[0]


def budget_alerts(conn, user_id, today):
    """Presupuestos que cruzan 80% o 100% este mes y no fueron avisados."""
    ym = today.strftime("%Y-%m")
    mes_ini = today.strftime("%Y-%m-01")
    out = []
    for b in conn.execute(
        "SELECT b.id, b.category_id, b.amount, c.name FROM budgets b "
        "JOIN categories c ON c.id=b.category_id WHERE b.user_id=?", (user_id,)).fetchall():
        if not b["amount"] or b["amount"] <= 0:
            continue
        spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='gasto' AND currency='ARS' "
            "AND kind='normal' AND category_id=? AND user_id=? AND occurred_at>=?",
            (b["category_id"], user_id, mes_ini)).fetchone()[0]
        pct = spent / b["amount"] * 100
        threshold = 100 if pct >= 100 else (80 if pct >= 80 else None)
        if threshold is None:
            continue
        ref = f"{b['id']}:{ym}:{threshold}"
        if already_sent(conn, user_id, "budget_warn", ref):
            continue
        out.append(("budget_warn", ref, f"⚠️ {b['name']}: usaste el {round(pct)}% de tu presupuesto"))
    return out


def card_alerts(conn, user_id, today):
    """Cierre en ≤3 días (card_closing) y vencimiento mañana (card_due), sin repetir."""
    out = []
    cards = conn.execute(
        "SELECT id, name, closing_day, due_day FROM accounts "
        "WHERE user_id=? AND type='credito' AND active=1", (user_id,)).fetchall()
    for c in cards:
        if not c["closing_day"] or not c["due_day"]:
            continue
        last_closing, next_closing, next_due = vencimientos.proximo_cierre_y_vencimiento(
            c["closing_day"], c["due_day"], today)
        d_close = (next_closing - today).days
        if 0 <= d_close <= 3:
            ref = f"{c['id']}:{next_closing.isoformat()}"
            if not already_sent(conn, user_id, "card_closing", ref):
                ciclo = _sum_card(conn, c["id"], last_closing.isoformat())
                out.append(("card_closing", ref,
                            f"💳 {c['name']} cierra en {d_close} días — llevás ${ciclo:,.0f}"))
        if (next_due - today).days == 1:
            ref = f"{c['id']}:{next_due.isoformat()}"
            if not already_sent(conn, user_id, "card_due", ref):
                prev_closing = last_closing - timedelta(days=31)
                resumen = _sum_card(conn, c["id"], prev_closing.isoformat(), last_closing.isoformat())
                out.append(("card_due", ref,
                            f"💳 Mañana vence {c['name']}: ${resumen:,.0f}"))
    return out


def pending_alerts(conn, user_id, today=None):
    today = today or date.today()
    return budget_alerts(conn, user_id, today) + card_alerts(conn, user_id, today)
