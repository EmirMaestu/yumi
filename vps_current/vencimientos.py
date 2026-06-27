"""
Modulo de proximo vencimiento de tarjetas de credito.

Provee:
- proximo_cierre_y_vencimiento(closing_day, due_day, today=None) -> (last_closing, next_closing, next_due)
- calcular_vencimiento(db_path, account, today=None) -> dict con totales
- registrar_handlers(application) para el bot (agrega /vencimientos)
- registrar_endpoint(app) para la web (agrega GET /api/vencimientos)
- proxima_fecha_para_cuota(closing_day, purchase_date) -> date  (usar en save_recurring)
"""

import sqlite3
import calendar
from datetime import date, datetime, timedelta
from pathlib import Path


def _last_day(year, month):
    return calendar.monthrange(year, month)[1]


def _safe_day(year, month, day):
    return min(day, _last_day(year, month))


def _shift_month(d: date, n: int) -> date:
    """Suma n meses a una fecha, ajustando el dia si no existe (29/30/31)."""
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, _safe_day(y, m, d.day))


def _venc_para_cierre(cierre_date, closing_day, due_day):
    """Fecha de vencimiento del resumen que cierra en `cierre_date`.
    Si el dia de vencimiento es MAYOR al de cierre -> vence el MISMO mes
    (ej. cierre 2 / venc 13 -> cierra 02/03, vence 13/03).
    Si es menor o igual -> vence el mes SIGUIENTE (ej. cierre 28 / venc 5)."""
    cd = max(1, min(31, closing_day or 1))
    dd = max(1, min(31, due_day or 10))
    if dd > cd:
        vy, vm = cierre_date.year, cierre_date.month
    else:
        vy = cierre_date.year + (1 if cierre_date.month == 12 else 0)
        vm = 1 if cierre_date.month == 12 else cierre_date.month + 1
    return date(vy, vm, _safe_day(vy, vm, dd))


def proximo_cierre_y_vencimiento(closing_day, due_day, today=None):
    """
    Para una tarjeta con dia de cierre y vencimiento, devuelve:
      last_closing       fecha del cierre anterior (resumen actual ya cerrado)
      next_closing       fecha del proximo cierre (donde caen las compras de hoy)
      next_due           proximo vencimiento que hay que pagar
    """
    today = today or date.today()
    cd = max(1, min(31, closing_day or 1))
    dd = max(1, min(31, due_day or 10))

    # cierre anterior
    if today.day > cd:
        last_y, last_m = today.year, today.month
    else:
        last_y = today.year - 1 if today.month == 1 else today.year
        last_m = 12 if today.month == 1 else today.month - 1
    last_closing = date(last_y, last_m, _safe_day(last_y, last_m, cd))

    # proximo cierre
    if today.day <= cd:
        next_closing = date(today.year, today.month, _safe_day(today.year, today.month, cd))
    else:
        ny = today.year + 1 if today.month == 12 else today.year
        nm = 1 if today.month == 12 else today.month + 1
        next_closing = date(ny, nm, _safe_day(ny, nm, cd))

    # vencimiento del resumen cerrado (last_closing): mismo mes o siguiente segun los dias
    next_due = _venc_para_cierre(last_closing, cd, dd)
    # si ya pasó, el proximo pago es el vencimiento del proximo cierre
    if next_due < today:
        next_due = _venc_para_cierre(next_closing, cd, dd)

    return last_closing, next_closing, next_due


def proxima_fecha_para_cuota(closing_day, purchase_date=None):
    """
    Devuelve la fecha de cierre en la que cae una compra hecha en `purchase_date`.
    - Si purchase_date <= cierre del mes actual -> cierre de este mes
    - Si no, cierre del mes siguiente
    Usar para setear `next_occurrence` de la primera cuota.
    """
    if not closing_day:
        return purchase_date or date.today()
    purchase_date = purchase_date or date.today()
    cd = max(1, min(31, closing_day))
    if purchase_date.day <= cd:
        return date(purchase_date.year, purchase_date.month, _safe_day(purchase_date.year, purchase_date.month, cd))
    ny = purchase_date.year + (1 if purchase_date.month == 12 else 0)
    nm = 1 if purchase_date.month == 12 else purchase_date.month + 1
    return date(ny, nm, _safe_day(ny, nm, cd))


def venc_de_cuota(closing_day, due_day, purchase_date=None):
    """Fecha de VENCIMIENTO en la que se paga una compra en cuotas hecha en `purchase_date`.
    = vencimiento del cierre donde postea la compra (misma convencion que el modulo:
    el vencimiento cae el due_day del mes siguiente al cierre). None si falta algun dato.
    Usar para setear `next_occurrence` de cuotas de tarjeta."""
    if not closing_day or not due_day:
        return None
    cierre = proxima_fecha_para_cuota(closing_day, purchase_date)
    return _venc_para_cierre(cierre, closing_day, due_day)


def calcular_vencimiento(db_path, account_row, today=None):
    """
    account_row: dict con id, name, type, closing_day, due_day, icon, currency_hint?, user_id
    Devuelve un dict listo para mostrar.
    """
    today = today or date.today()
    cd = account_row.get("closing_day")
    dd = account_row.get("due_day")
    out = {
        "account_id": account_row["id"],
        "account_name": account_row.get("name"),
        "icon": account_row.get("icon"),
        "user_id": account_row.get("user_id"),
    }
    if not cd or not dd:
        out["error"] = "Falta closing_day/due_day. Corre migrate_tarjetas.py."
        return out

    last_closing, next_closing, next_due = proximo_cierre_y_vencimiento(cd, dd, today)
    # ciclo cerrado: desde (cierre_anteanterior + 1) hasta last_closing
    prev_prev = _shift_month(last_closing, -1)
    cycle_start = prev_prev + timedelta(days=1)

    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    # OJO: excluimos las transacciones generadas por recurrentes (recurring_id IS NOT NULL):
    # las cuotas/suscripciones se cuentan UNA sola vez vía el plan (recurrenteMensual en
    # el front), no como transacción del ciclo. Si no, se duplicaban.
    rows = conn.execute(
        "SELECT currency, SUM(amount) AS s FROM transactions "
        "WHERE account_id=? AND type='gasto' AND recurring_id IS NULL AND DATE(occurred_at) BETWEEN ? AND ? "
        "GROUP BY currency",
        (account_row["id"], cycle_start.isoformat(), last_closing.isoformat())).fetchall()
    # gastos que caen en el ciclo ACTUAL (todavia abierto, vencen al siguiente)
    rows_open = conn.execute(
        "SELECT currency, SUM(amount) AS s FROM transactions "
        "WHERE account_id=? AND type='gasto' AND recurring_id IS NULL AND DATE(occurred_at) BETWEEN ? AND ? "
        "GROUP BY currency",
        (account_row["id"], (last_closing + timedelta(days=1)).isoformat(),
         next_closing.isoformat())).fetchall()
    conn.close()

    out.update({
        "last_closing": last_closing.isoformat(),
        "next_closing": next_closing.isoformat(),
        "next_due": next_due.isoformat(),
        "ciclo_cerrado": [{"currency": r["currency"], "total": r["s"]} for r in rows],
        "ciclo_abierto": [{"currency": r["currency"], "total": r["s"]} for r in rows_open],
    })
    return out


# ─── Bot (telegram) integration ───────────────────────────────────────────
def registrar_handlers(application, db_path, is_allowed_fn, current_user_id_fn):
    """
    Agrega el handler de /vencimientos al Application del bot.
    Pasame las funciones is_allowed y current_user_id de tu main.py.
    """
    from telegram.ext import CommandHandler

    async def vencimientos_cmd(update, context):
        if not is_allowed_fn(update): return
        uid = current_user_id_fn(update)
        conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
        cards = conn.execute(
            "SELECT * FROM accounts WHERE type='credito' AND active=1 AND user_id=? ORDER BY name",
            (uid,)).fetchall()
        conn.close()
        if not cards:
            await update.message.reply_text("No tenes tarjetas de credito activas."); return
        today = date.today()
        msg = "💳 Proximos vencimientos\n\n"
        for c in cards:
            d = calcular_vencimiento(db_path, dict(c), today)
            msg += f"{c['icon'] or '💳'} {c['name']}\n"
            if d.get("error"):
                msg += f"   ⚠️ {d['error']}\n\n"; continue
            for r in d["ciclo_cerrado"]:
                msg += f"   A pagar el {d['next_due']}: {r['total']:,.2f} {r['currency']}\n"
            if not d["ciclo_cerrado"]:
                msg += f"   A pagar el {d['next_due']}: sin movimientos en el ciclo cerrado\n"
            for r in d["ciclo_abierto"]:
                msg += f"   Acumulado mes en curso (cierra {d['next_closing']}): {r['total']:,.2f} {r['currency']}\n"
            msg += "\n"
        await update.message.reply_text(msg)

    application.add_handler(CommandHandler("vencimientos", vencimientos_cmd))


# ─── Web (FastAPI) integration ────────────────────────────────────────────
def registrar_endpoint(app, db_path, require_user_dep, resolve_scope_uid_fn):
    """Agrega GET /api/vencimientos al FastAPI app.
    require_user_dep: dependencia Depends(require_user) de web.py
    resolve_scope_uid_fn: funcion para resolver scope cookie a user_id.
    """
    from fastapi import Depends, Cookie

    @app.get("/api/vencimientos")
    def api_vencimientos(user=Depends(require_user_dep), scope: str = Cookie("mine")):
        scope_uid = resolve_scope_uid_fn(scope, user)
        today = date.today()
        conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
        if scope_uid is None:
            cards = conn.execute(
                "SELECT * FROM accounts WHERE type='credito' AND active=1 ORDER BY name").fetchall()
        else:
            cards = conn.execute(
                "SELECT * FROM accounts WHERE type='credito' AND active=1 AND user_id=? ORDER BY name",
                (scope_uid,)).fetchall()
        conn.close()
        return [calcular_vencimiento(db_path, dict(c), today) for c in cards]
