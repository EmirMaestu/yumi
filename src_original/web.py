import os
import csv
import json
import sqlite3
import urllib.request
import time as _time
import io
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, StreamingResponse
from crud_v2 import router as crud_v2_router, init_crud_v2

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
TIMEZONE = os.environ.get("TIMEZONE", "America/Argentina/Buenos_Aires")
TZ = ZoneInfo(TIMEZONE)
DB_PATH = BASE_DIR / "data.db"
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]

_rate_cache = {}
RATE_TTL = 900

app = FastAPI(title="Asistente Dashboard")
init_crud_v2()
app.include_router(crud_v2_router)


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try: yield conn
    finally: conn.close()


def now_local(): return datetime.now(TZ)


def get_dolar_rate(rate_type="blue"):
    now = _time.time()
    if rate_type in _rate_cache:
        ts, value = _rate_cache[rate_type]
        if now - ts < RATE_TTL: return value
    try:
        with urllib.request.urlopen(f"https://dolarapi.com/v1/dolares/{rate_type}", timeout=5) as r:
            data = json.loads(r.read().decode())
        rate = (data.get("compra",0) + data.get("venta",0)) / 2
        if not rate: return None
        _rate_cache[rate_type] = (now, rate)
        return rate
    except Exception: return None


# ---------- Overview ----------
@app.get("/api/overview")
def api_overview():
    now = now_local()
    mes_ini = now.strftime("%Y-%m-01")
    nowstr = now.strftime("%Y-%m-%dT%H:%M")
    with db() as conn:
        accounts = [dict(r) for r in conn.execute("SELECT * FROM accounts WHERE active=1 ORDER BY name").fetchall()]
        bals = conn.execute(
            "SELECT account_id, currency, SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS bal "
            "FROM transactions GROUP BY account_id, currency").fetchall()
        m = {}
        for r in bals: m.setdefault(r['account_id'], []).append({"currency": r['currency'], "balance": r['bal']})
        for a in accounts: a['balances'] = m.get(a['id'], [])

        # Credit cards: pending cuotas
        for a in accounts:
            if a['type'] == 'credito':
                pendientes = conn.execute(
                    "SELECT id, amount, currency, description, total_installments, installments_fired "
                    "FROM recurring WHERE active=1 AND account_id=?", (a['id'],)).fetchall()
                cuotas_pendientes = []
                for r in pendientes:
                    total = r['total_installments']
                    fired = r['installments_fired'] or 0
                    remaining = (total - fired) if total else None
                    cuotas_pendientes.append({
                        "description": r['description'], "amount": r['amount'], "currency": r['currency'],
                        "remaining": remaining, "total": total, "fired": fired,
                        "total_pending": r['amount'] * remaining if remaining else None,
                    })
                a['pending_cuotas'] = cuotas_pendientes
            else:
                a['pending_cuotas'] = []

        tot_mes = [dict(r) for r in conn.execute(
            "SELECT type, currency, SUM(amount) AS total FROM transactions WHERE occurred_at>=? GROUP BY type, currency", (mes_ini,)).fetchall()]
        por_cat = [dict(r) for r in conn.execute(
            "SELECT COALESCE(c.name,'(sin categoría)') AS cat, c.color AS color, c.icon AS icon, t.currency, SUM(t.amount) AS total "
            "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            "WHERE t.occurred_at>=? AND t.type='gasto' GROUP BY cat, t.currency ORDER BY total DESC", (mes_ini,)).fetchall()]
        por_acc = [dict(r) for r in conn.execute(
            "SELECT a.name AS acc, a.color AS color, a.icon AS icon, t.currency, SUM(t.amount) AS total FROM transactions t "
            "JOIN accounts a ON a.id=t.account_id WHERE t.occurred_at>=? AND t.type='gasto' "
            "GROUP BY a.name, t.currency ORDER BY total DESC", (mes_ini,)).fetchall()]
        counts = {
            "eventos_proximos": conn.execute("SELECT COUNT(*) FROM eventos WHERE starts_at>=?", (nowstr,)).fetchone()[0],
            "tareas_pendientes": conn.execute("SELECT COUNT(*) FROM tareas WHERE status='pendiente'").fetchone()[0],
            "recordatorios": conn.execute("SELECT COUNT(*) FROM recordatorios WHERE fired=0 AND remind_at>=?", (nowstr,)).fetchone()[0],
            "recurrentes": conn.execute("SELECT COUNT(*) FROM recurring WHERE active=1").fetchone()[0],
            "notas": conn.execute("SELECT COUNT(*) FROM notas").fetchone()[0],
        }
    return {"accounts": accounts, "totales_mes": tot_mes, "por_categoria": por_cat,
            "por_cuenta": por_acc, "counts": counts, "mes_nombre": MESES[now.month-1], "year": now.year}


# ---------- Overview v2 (rediseño) ----------
@app.get("/api/overview2")
def api_overview2():
    now = now_local()
    mes_ini = now.strftime("%Y-%m-01")
    hoy = now.strftime("%Y-%m-%d")
    blue = get_dolar_rate("blue") or 0

    def ars(amount, currency):
        return amount * (blue if currency in ("USD", "EUR") and blue else 1)

    # mes anterior a la misma altura
    prev_last = now.replace(day=1) - timedelta(days=1)
    prev_ini = prev_last.strftime("%Y-%m-01")
    prev_alt = prev_last.replace(day=min(now.day, prev_last.day)).strftime("%Y-%m-%dT%H:%M")

    with db() as conn:
        accounts = [dict(r) for r in conn.execute("SELECT * FROM accounts WHERE active=1 ORDER BY name").fetchall()]
        bals = conn.execute(
            "SELECT account_id, currency, SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS bal "
            "FROM transactions GROUP BY account_id, currency").fetchall()
        balmap = {}
        for r in bals: balmap.setdefault(r["account_id"], []).append(dict(r))

        patrimonio = 0.0; deuda = 0.0; disponible = 0.0
        for a in accounts:
            for b in balmap.get(a["id"], []):
                v = ars(b["bal"], b["currency"])
                patrimonio += v
                if a["type"] == "credito" and v < 0: deuda += -v
                if a["type"] not in ("credito",) and v > 0: disponible += v

        cuotas_futuras = 0.0; cuotas_n = 0
        for r in conn.execute("SELECT amount,currency,total_installments,installments_fired FROM recurring "
                              "WHERE active=1 AND total_installments IS NOT NULL").fetchall():
            rem = r["total_installments"] - (r["installments_fired"] or 0)
            if rem > 0:
                cuotas_futuras += ars(r["amount"], r["currency"]) * rem; cuotas_n += rem

        def suma(tipo, desde, hasta=None):
            q = ("SELECT t.currency, SUM(t.amount) AS s FROM transactions t "
                 "LEFT JOIN categories c ON c.id=t.category_id "
                 "WHERE t.type=? AND COALESCE(c.name,'')!='Transferencia' AND t.occurred_at>=?")
            params = [tipo, desde]
            if hasta: q += " AND t.occurred_at<=?"; params.append(hasta)
            q += " GROUP BY t.currency"
            return sum(ars(r["s"], r["currency"]) for r in conn.execute(q, params).fetchall())

        gasto_mes = suma("gasto", mes_ini)
        gasto_prev_alt = suma("gasto", prev_ini, prev_alt)
        ingreso_mes = suma("ingreso", mes_ini)

        # cashflow últimos 6 meses (ARS-equivalente, sin transferencias)
        first = (now.replace(day=1) - timedelta(days=155)).strftime("%Y-%m-01")
        cf = {}
        for r in conn.execute(
            "SELECT substr(t.occurred_at,1,7) AS ym, t.type, t.currency, SUM(t.amount) AS s "
            "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            "WHERE t.occurred_at>=? AND COALESCE(c.name,'')!='Transferencia' "
            "GROUP BY ym, t.type, t.currency", (first,)).fetchall():
            d = cf.setdefault(r["ym"], {"ingresos": 0, "gastos": 0})
            d["ingresos" if r["type"] == "ingreso" else "gastos"] += ars(r["s"], r["currency"])
        cashflow = [{"ym": k, **v} for k, v in sorted(cf.items())][-6:]

        # panel "Hoy"
        hoy_items = []
        for r in conn.execute("SELECT id,title,starts_at,location FROM eventos WHERE substr(starts_at,1,10)=? ORDER BY starts_at", (hoy,)).fetchall():
            hoy_items.append({"tipo": "evento", "titulo": r["title"], "sub": r["location"] or "", "hora": r["starts_at"][11:16]})
        for r in conn.execute("SELECT id,text,remind_at FROM recordatorios WHERE fired=0 AND substr(REPLACE(remind_at,' ','T'),1,10)=? ORDER BY remind_at", (hoy,)).fetchall():
            hoy_items.append({"tipo": "recordatorio", "titulo": r["text"], "sub": "Recordatorio", "hora": r["remind_at"].replace(' ', 'T')[11:16]})
        for r in conn.execute("SELECT id,text,priority FROM tareas WHERE status='pendiente' AND substr(COALESCE(due_at,''),1,10)<=? AND due_at IS NOT NULL ORDER BY priority", (hoy,)).fetchall():
            hoy_items.append({"tipo": "tarea", "titulo": r["text"], "sub": f"Tarea · prioridad {r['priority']}", "hora": "hoy"})
        for r in conn.execute("SELECT id,description,amount,currency FROM recurring WHERE active=1 AND next_occurrence<=? ORDER BY next_occurrence LIMIT 5", (hoy,)).fetchall():
            hoy_items.append({"tipo": "recurrente", "titulo": f"{r['description']} ${r['amount']:,.0f}", "sub": "Recurrente · se cobra hoy", "hora": "auto"})

        # top categorías del mes (para el donut)
        por_cat = [dict(r) for r in conn.execute(
            "SELECT COALESCE(c.name,'(sin categoría)') AS cat, c.color AS color, SUM(t.amount) AS total "
            "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            "WHERE t.occurred_at>=? AND t.type='gasto' AND t.currency='ARS' AND COALESCE(c.name,'')!='Transferencia' "
            "GROUP BY cat ORDER BY total DESC LIMIT 8", (mes_ini,)).fetchall()]

    return {
        "patrimonio_ars": patrimonio, "patrimonio_usd": (patrimonio / blue) if blue else None, "blue": blue,
        "kpis": {"gasto_mes": gasto_mes, "gasto_prev_alt": gasto_prev_alt, "ingreso_mes": ingreso_mes,
                 "deuda_tarjetas": deuda, "cuotas_futuras": cuotas_futuras, "cuotas_n": cuotas_n,
                 "disponible": disponible},
        "cashflow": cashflow, "hoy": hoy_items, "por_categoria": por_cat,
        "mes_nombre": MESES[now.month-1], "year": now.year, "dia": now.day,
    }


# ---------- Accounts CRUD ----------
@app.get("/api/accounts")
def api_accounts(include_inactive: bool = False):
    with db() as conn:
        if include_inactive:
            rows = conn.execute("SELECT * FROM accounts ORDER BY active DESC, name").fetchall()
        else:
            rows = conn.execute("SELECT * FROM accounts WHERE active=1 ORDER BY name").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/accounts")
def api_acc_create(body: dict = Body(...)):
    name = (body.get("name") or "").strip()
    if not name: raise HTTPException(400, "Nombre requerido")
    with db() as conn:
        exists = conn.execute("SELECT id FROM accounts WHERE name=?", (name,)).fetchone()
        if exists: raise HTTPException(400, "Ya existe una cuenta con ese nombre")
        cur = conn.execute("INSERT INTO accounts (name,type,color,icon,active) VALUES (?,?,?,?,1)",
            (name, body.get("type","efectivo"), body.get("color","#60a5fa"), body.get("icon","💳")))
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


@app.patch("/api/accounts/{aid}")
def api_acc_update(aid: int, body: dict = Body(...)):
    fields=[]; params=[]
    for k in ("name","type","color","icon"):
        if k in body: fields.append(f"{k}=?"); params.append(body[k])
    if "active" in body: fields.append("active=?"); params.append(1 if body["active"] else 0)
    if not fields: raise HTTPException(400, "Sin cambios")
    params.append(aid)
    with db() as conn:
        conn.execute(f"UPDATE accounts SET {', '.join(fields)} WHERE id=?", params); conn.commit()
    return {"ok": True}


@app.delete("/api/accounts/{aid}")
def api_acc_delete(aid: int):
    with db() as conn:
        in_use = conn.execute("SELECT COUNT(*) FROM transactions WHERE account_id=?", (aid,)).fetchone()[0]
        if in_use:
            conn.execute("UPDATE accounts SET active=0 WHERE id=?", (aid,))
            conn.commit()
            return {"ok": True, "archived": True}
        conn.execute("DELETE FROM accounts WHERE id=?", (aid,)); conn.commit()
    return {"ok": True}


# ---------- Categories CRUD ----------
@app.get("/api/categories")
def api_categories(include_inactive: bool = False):
    with db() as conn:
        if include_inactive:
            rows = conn.execute("SELECT * FROM categories ORDER BY active DESC, type, name").fetchall()
        else:
            rows = conn.execute("SELECT * FROM categories WHERE active=1 ORDER BY type, name").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/categories")
def api_cat_create(body: dict = Body(...)):
    name = (body.get("name") or "").strip()
    if not name: raise HTTPException(400, "Nombre requerido")
    with db() as conn:
        if conn.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone():
            raise HTTPException(400, "Ya existe")
        cur = conn.execute("INSERT INTO categories (name,type,color,icon,active) VALUES (?,?,?,?,1)",
            (name, body.get("type","gasto"), body.get("color","#94a3b8"), body.get("icon","📦")))
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


@app.patch("/api/categories/{cid}")
def api_cat_update(cid: int, body: dict = Body(...)):
    fields=[]; params=[]
    for k in ("name","type","color","icon"):
        if k in body: fields.append(f"{k}=?"); params.append(body[k])
    if "active" in body: fields.append("active=?"); params.append(1 if body["active"] else 0)
    if not fields: raise HTTPException(400, "Sin cambios")
    params.append(cid)
    with db() as conn:
        conn.execute(f"UPDATE categories SET {', '.join(fields)} WHERE id=?", params); conn.commit()
    return {"ok": True}


@app.delete("/api/categories/{cid}")
def api_cat_delete(cid: int):
    with db() as conn:
        in_use = conn.execute("SELECT COUNT(*) FROM transactions WHERE category_id=?", (cid,)).fetchone()[0]
        if in_use:
            conn.execute("UPDATE categories SET active=0 WHERE id=?", (cid,)); conn.commit()
            return {"ok": True, "archived": True}
        conn.execute("DELETE FROM categories WHERE id=?", (cid,)); conn.commit()
    return {"ok": True}


# ---------- Transactions ----------
@app.get("/api/transactions")
def api_transactions(year: int = None, month: int = None, account_id: int = None,
                      category_id: int = None, currency: str = None, type: str = None,
                      q: str = None, limit: int = 200, offset: int = 0):
    where = []; params = []
    if year and month:
        start = f"{year}-{month:02d}-01"
        em, ey = (month+1, year) if month < 12 else (1, year+1)
        end = f"{ey}-{em:02d}-01"
        where.append("t.occurred_at >= ? AND t.occurred_at < ?"); params.extend([start, end])
    if account_id: where.append("t.account_id = ?"); params.append(account_id)
    if category_id == -1: where.append("t.category_id IS NULL")
    elif category_id: where.append("t.category_id = ?"); params.append(category_id)
    if currency: where.append("t.currency = ?"); params.append(currency)
    if type: where.append("t.type = ?"); params.append(type)
    if q: where.append("LOWER(COALESCE(t.description,'')) LIKE LOWER(?)"); params.append(f"%{q}%")
    wc = " AND ".join(where) if where else "1=1"
    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM transactions t WHERE {wc}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT t.*, a.name AS acc_name, a.color AS acc_color, a.icon AS acc_icon, "
            f"c.name AS cat_name, c.color AS cat_color, c.icon AS cat_icon, "
            f"r.description AS rec_desc, r.total_installments AS rec_total, r.installments_fired AS rec_fired "
            f"FROM transactions t JOIN accounts a ON a.id=t.account_id "
            f"LEFT JOIN categories c ON c.id=t.category_id "
            f"LEFT JOIN recurring r ON r.id=t.recurring_id "
            f"WHERE {wc} ORDER BY t.occurred_at DESC, t.id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]).fetchall()
        sums = conn.execute(f"SELECT t.type, t.currency, SUM(t.amount) AS total FROM transactions t WHERE {wc} GROUP BY t.type, t.currency", params).fetchall()
    return {"items": [dict(r) for r in rows], "total": total, "sums": [dict(r) for r in sums]}


@app.post("/api/transactions")
def api_tx_create(body: dict = Body(...)):
    required = ("amount", "account_id", "occurred_at", "type")
    for k in required:
        if k not in body or body[k] is None: raise HTTPException(400, f"Falta {k}")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (body["type"], float(body["amount"]), body.get("currency","ARS"),
             int(body["account_id"]), int(body["category_id"]) if body.get("category_id") else None,
             body.get("description"), body["occurred_at"]))
        conn.commit()
    return {"id": cur.lastrowid, "ok": True}


@app.patch("/api/transactions/{tid}")
def api_patch_tx(tid: int, body: dict = Body(...)):
    fields=[]; params=[]
    for k in ("amount","currency","description","occurred_at","type"):
        if k in body: fields.append(f"{k}=?"); params.append(body[k])
    if "account_id" in body: fields.append("account_id=?"); params.append(int(body["account_id"]))
    if "category_id" in body:
        v = body["category_id"]; fields.append("category_id=?")
        params.append(int(v) if v else None)
    if not fields: raise HTTPException(400, "Sin cambios")
    params.append(tid)
    with db() as conn:
        conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id=?", params); conn.commit()
    return {"ok": True}


@app.delete("/api/transactions/{tid}")
def del_tx(tid: int):
    with db() as conn:
        conn.execute("DELETE FROM transactions WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.post("/api/transactions/bulk_delete")
def bulk_delete_tx(body: dict = Body(...)):
    ids = body.get("ids") or []
    if not ids: raise HTTPException(400, "Sin ids")
    placeholders = ",".join("?" * len(ids))
    with db() as conn:
        conn.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", ids); conn.commit()
    return {"ok": True, "count": len(ids)}


@app.post("/api/transactions/bulk_move")
def bulk_move_tx(body: dict = Body(...)):
    ids = body.get("ids") or []
    if not ids: raise HTTPException(400, "Sin ids")
    sets = []; params = []
    if body.get("account_id"): sets.append("account_id=?"); params.append(int(body["account_id"]))
    if body.get("category_id"): sets.append("category_id=?"); params.append(int(body["category_id"]))
    if not sets: raise HTTPException(400, "Sin cambios")
    placeholders = ",".join("?" * len(ids))
    with db() as conn:
        conn.execute(f"UPDATE transactions SET {', '.join(sets)} WHERE id IN ({placeholders})", params + ids)
        conn.commit()
    return {"ok": True, "count": len(ids)}


@app.get("/api/export.csv")
def export_csv(year: int = None, month: int = None):
    where = []; params = []
    if year and month:
        start = f"{year}-{month:02d}-01"
        em, ey = (month+1, year) if month < 12 else (1, year+1)
        end = f"{ey}-{em:02d}-01"
        where.append("t.occurred_at >= ? AND t.occurred_at < ?"); params.extend([start, end])
    wc = " AND ".join(where) if where else "1=1"
    with db() as conn:
        rows = conn.execute(
            f"SELECT t.id, t.occurred_at, t.type, t.amount, t.currency, a.name AS account, "
            f"c.name AS category, t.description FROM transactions t JOIN accounts a ON a.id=t.account_id "
            f"LEFT JOIN categories c ON c.id=t.category_id WHERE {wc} ORDER BY t.occurred_at DESC", params).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id","fecha","tipo","monto","moneda","cuenta","categoria","descripcion"])
    for r in rows:
        w.writerow([r['id'], r['occurred_at'], r['type'], r['amount'], r['currency'],
                    r['account'], r['category'] or '', r['description'] or ''])
    buf.seek(0)
    fn = f"transacciones_{year}_{month:02d}.csv" if year and month else "transacciones.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fn}"})


# ---------- Recurring ----------
@app.get("/api/recurring")
def api_recurring(include_inactive: bool = False):
    with db() as conn:
        sql = ("SELECT r.*, a.name AS acc_name, a.color AS acc_color, a.icon AS acc_icon, "
               "c.name AS cat_name, c.color AS cat_color, c.icon AS cat_icon "
               "FROM recurring r JOIN accounts a ON a.id=r.account_id "
               "LEFT JOIN categories c ON c.id=r.category_id ")
        if not include_inactive: sql += "WHERE r.active=1 "
        sql += "ORDER BY r.active DESC, r.next_occurrence"
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


@app.patch("/api/recurring/{rid}")
def api_patch_rec(rid: int, body: dict = Body(...)):
    fields=[]; params=[]
    for k in ("amount","description","day_of_month","next_occurrence","total_installments"):
        if k in body: fields.append(f"{k}=?"); params.append(body[k])
    if "active" in body: fields.append("active=?"); params.append(1 if body["active"] else 0)
    if not fields: raise HTTPException(400, "Sin cambios")
    params.append(rid)
    with db() as conn:
        conn.execute(f"UPDATE recurring SET {', '.join(fields)} WHERE id=?", params); conn.commit()
    return {"ok": True}


@app.delete("/api/recurring/{rid}")
def del_rec_rec(rid: int):
    with db() as conn:
        conn.execute("DELETE FROM recurring WHERE id=?", (rid,)); conn.commit()
    return {"ok": True}


# ---------- Resto: eventos, tareas, hábitos, recordatorios, notas, cotización ----------
@app.get("/api/eventos")
def api_eventos(past: bool = False):
    nowstr = now_local().strftime("%Y-%m-%dT%H:%M")
    with db() as conn:
        if past: rows = conn.execute("SELECT * FROM eventos WHERE starts_at<? ORDER BY starts_at DESC LIMIT 50", (nowstr,)).fetchall()
        else: rows = conn.execute("SELECT * FROM eventos WHERE starts_at>=? ORDER BY starts_at ASC", (nowstr,)).fetchall()
    return [dict(r) for r in rows]


@app.delete("/api/eventos/{eid}")
def del_ev(eid: int):
    with db() as conn: conn.execute("DELETE FROM eventos WHERE id=?", (eid,)); conn.commit()
    return {"ok": True}


@app.get("/api/tareas")
def api_tareas(status: str = "pendiente"):
    with db() as conn:
        if status == "all":
            rows = conn.execute("SELECT * FROM tareas ORDER BY created_at DESC LIMIT 200").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tareas WHERE status=? ORDER BY "
                "CASE priority WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, "
                "COALESCE(due_at,'9999'), id", (status,)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/tareas")
def crear_tarea(body: dict = Body(...)):
    text = (body.get("text") or "").strip()
    if not text: raise HTTPException(400, "Texto requerido")
    with db() as conn:
        cur = conn.execute("INSERT INTO tareas (text,priority,due_at) VALUES (?,?,?)",
            (text, body.get("priority","media"), body.get("due_at")))
        conn.commit()
    return {"id": cur.lastrowid, "ok": True}


@app.post("/api/tareas/{tid}/done")
def t_done(tid: int):
    with db() as conn:
        conn.execute("UPDATE tareas SET status='hecha', completed_at=datetime('now') WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.post("/api/tareas/{tid}/undone")
def t_undone(tid: int):
    with db() as conn:
        conn.execute("UPDATE tareas SET status='pendiente', completed_at=NULL WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.delete("/api/tareas/{tid}")
def del_tar(tid: int):
    with db() as conn: conn.execute("DELETE FROM tareas WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.get("/api/habitos")
def api_habitos(days: int = 30):
    desde = (now_local() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with db() as conn:
        items = [dict(r) for r in conn.execute("SELECT * FROM habito_logs WHERE logged_at>=? ORDER BY logged_at DESC", (desde,)).fetchall()]
        resumen = [dict(r) for r in conn.execute(
            "SELECT name, COUNT(*) AS cnt, SUM(value) AS total, unit FROM habito_logs "
            "WHERE logged_at>=? GROUP BY name, unit ORDER BY cnt DESC", (desde,)).fetchall()]
    return {"items": items, "resumen": resumen, "days": days}


@app.get("/api/recordatorios")
def api_recs(include_fired: bool = False):
    with db() as conn:
        if include_fired:
            rows = conn.execute("SELECT * FROM recordatorios ORDER BY remind_at DESC LIMIT 100").fetchall()
        else:
            rows = conn.execute("SELECT * FROM recordatorios WHERE fired=0 ORDER BY remind_at ASC").fetchall()
    return [dict(r) for r in rows]


@app.delete("/api/recordatorios/{rid}")
def del_rec(rid: int):
    with db() as conn: conn.execute("DELETE FROM recordatorios WHERE id=?", (rid,)); conn.commit()
    return {"ok": True}


@app.get("/api/notas")
def api_notas(q: str = None, limit: int = 50):
    with db() as conn:
        if q: rows = conn.execute("SELECT * FROM notas WHERE text LIKE ? ORDER BY created_at DESC LIMIT ?", (f"%{q}%", limit)).fetchall()
        else: rows = conn.execute("SELECT * FROM notas ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/notas")
def crear_nota(body: dict = Body(...)):
    text = (body.get("text") or "").strip()
    if not text: raise HTTPException(400, "Texto requerido")
    tags = json.dumps(body.get("tags") or [], ensure_ascii=False)
    with db() as conn:
        cur = conn.execute("INSERT INTO notas (text,tags) VALUES (?,?)", (text, tags)); conn.commit()
    return {"id": cur.lastrowid, "ok": True}


@app.delete("/api/notas/{nid}")
def del_nota(nid: int):
    with db() as conn: conn.execute("DELETE FROM notas WHERE id=?", (nid,)); conn.commit()
    return {"ok": True}


@app.get("/api/cotizacion")
def api_cotizacion():
    return {t: get_dolar_rate(t) for t in ["oficial","blue","mep","cripto"]}


HTML = r"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mi Asistente</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root{
  --bg:#0b0e14; --surface:#121724; --surface-2:#1a2133; --border:#232c42;
  --text:#e8ecf4; --text-2:#8b95ab; --text-3:#5a6478;
  --accent:#6c8cff; --accent-2:#1e40af; --accent-soft:rgba(108,140,255,.14);
  --green:#34d399; --red:#f87171; --amber:#fbbf24;
  --green-soft:rgba(52,211,153,.12); --red-soft:rgba(248,113,113,.12);
  --radius:13px; --radius-sm:8px; --shadow:0 8px 24px rgba(0,0,0,.35);
}
[data-theme="light"]{
  --bg:#f4f6fb; --surface:#ffffff; --surface-2:#eef1f8; --border:#e2e7f0;
  --text:#1a2233; --text-2:#5d6a82; --text-3:#9aa5b8;
  --accent-soft:rgba(108,140,255,.12); --shadow:0 8px 24px rgba(30,40,70,.08);
}
*{box-sizing:border-box}
body{font-family:'Inter',-apple-system,'Segoe UI',Roboto,sans-serif;margin:0;background:var(--bg);color:var(--text);min-height:100vh;padding-bottom:80px;font-size:14px}
.num,.amt,.card .v,.kpi .v,.hero .big{font-variant-numeric:tabular-nums}
header{background:var(--surface);padding:10px 20px;border-bottom:1px solid var(--border);display:flex;gap:12px;align-items:center;position:fixed;top:0;left:0;right:0;z-index:70;height:52px}
h1{font-size:15px;margin:0;font-weight:800;letter-spacing:-.01em}
.topbar-actions{margin-left:auto;display:flex;gap:8px}
.kbd-lbl{font-size:11px;color:var(--text-3)}
.sidebar{position:fixed;top:52px;left:0;bottom:0;width:218px;background:var(--surface);border-right:1px solid var(--border);padding:14px 10px;overflow-y:auto;z-index:60}
.nav-label{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--text-3);padding:12px 10px 5px;font-weight:700}
.nav-item{display:flex;align-items:center;gap:9px;width:100%;text-align:left;padding:7px 10px;border-radius:var(--radius-sm);color:var(--text-2);cursor:pointer;font-weight:500;margin-bottom:1px;border:none;background:none;font-size:13px;font-family:inherit;transition:background .12s,color .12s}
.nav-item:hover{background:var(--surface-2);color:var(--text)}
.nav-item.active{background:var(--accent-soft);color:var(--accent);font-weight:600}
.nav-bottom{display:none;position:fixed;bottom:0;left:0;right:0;background:var(--surface);border-top:1px solid var(--border);padding:5px 2px calc(5px + env(safe-area-inset-bottom));justify-content:space-around;z-index:60}
.nav-bottom button{background:none;border:none;color:var(--text-3);font-size:10px;font-weight:600;padding:4px 6px;display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;flex:1;font-family:inherit}
.nav-bottom button.active{color:var(--accent)}
.nav-bottom .ico{font-size:18px}
main{padding:72px 24px 20px;max-width:1240px;margin:0 auto 0 218px}
@media(max-width:900px){.sidebar{display:none}main{margin:0 auto;padding:68px 12px 90px}.nav-bottom{display:flex}body{padding-bottom:70px}}
.section{display:none}.section.active{display:block;animation:fadeUp .22s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.hero{background:linear-gradient(135deg,var(--surface) 0%,var(--surface-2) 100%);border:1px solid var(--border);border-radius:var(--radius);padding:20px 24px;margin-bottom:16px;box-shadow:var(--shadow)}
.hero .l{font-size:11px;color:var(--text-2);font-weight:600;letter-spacing:.04em}
.hero .big{font-size:32px;font-weight:800;letter-spacing:-.03em;margin-top:2px}
.hero .s{font-size:13px;margin-top:3px}
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin-bottom:16px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px}
.kpi .l{font-size:11.5px;color:var(--text-2);font-weight:600}
.kpi .v{font-size:21px;font-weight:800;margin-top:5px;letter-spacing:-.02em}
.kpi .s{font-size:11.5px;color:var(--text-3);margin-top:3px}
.kpi .v.pos,.pos{color:var(--green)}.kpi .v.neg,.neg{color:var(--red)}
.gridB{display:grid;grid-template-columns:1.55fr 1fr;gap:16px;margin-bottom:16px}
@media(max-width:900px){.kpi-row{grid-template-columns:1fr 1fr}.gridB{grid-template-columns:1fr}}
.today-item{display:flex;align-items:center;gap:11px;padding:9px 0;border-bottom:1px solid var(--border)}
.today-item:last-child{border-bottom:none}
.t-ico{width:32px;height:32px;border-radius:9px;display:grid;place-items:center;font-size:14px;background:var(--surface-2);flex-shrink:0}
.t-t{font-weight:600;font-size:13px}.t-s{font-size:11.5px;color:var(--text-3)}
.t-time{margin-left:auto;color:var(--text-3);font-size:12px;font-weight:600;white-space:nowrap}
.brow{margin-bottom:13px}.brow:last-child{margin-bottom:0}
.btop{display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:5px;gap:8px}
.btop span:first-child{font-weight:600}
.bbar{height:7px;background:var(--surface-2);border-radius:99px;overflow:hidden}
.bbar i{display:block;height:100%;border-radius:99px;background:var(--accent);transition:width .7s cubic-bezier(.22,1,.36,1)}
.bbar i.warn{background:var(--amber)}.bbar i.over{background:var(--red)}
.hm-grid{display:grid;grid-template-rows:repeat(7,9px);grid-auto-flow:column;grid-auto-columns:9px;gap:3px;overflow-x:auto;padding-bottom:4px}
.hm-cell{border-radius:2px;background:var(--surface-2)}
.hm-2{background:rgba(52,211,153,.45)}.hm-4{background:var(--green)}
.hm-block{margin-bottom:18px}
.hm-head{display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px;flex-wrap:wrap;gap:6px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:6px}
.card{background:var(--surface);padding:14px;border-radius:var(--radius);border:1px solid var(--border)}
.card .l{font-size:10px;color:var(--text-2);text-transform:uppercase;letter-spacing:.5px}
.card .v{font-size:20px;font-weight:700;margin-top:4px}
.card .s{font-size:11px;color:var(--text-2);margin-top:2px}
.panel{background:var(--surface);border-radius:var(--radius);border:1px solid var(--border);padding:17px;margin-bottom:16px}
.panel-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:13px;flex-wrap:wrap;gap:8px}
.panel h2{margin:0 0 10px;font-size:12px;color:var(--text-2);text-transform:uppercase;letter-spacing:.06em;font-weight:700}
.panel-head h2{margin:0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}.cards{grid-template-columns:repeat(2,1fr)}}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:9px 10px;background:var(--bg);color:var(--text-3);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid var(--border)}
td{padding:9px 10px;border-top:1px solid var(--border);vertical-align:middle}
tr:hover td{background:var(--surface-2)}
.btn{background:var(--surface-2);border:1px solid var(--border);color:var(--text);padding:6px 12px;border-radius:var(--radius-sm);cursor:pointer;font-size:12.5px;font-weight:600;font-family:inherit;transition:filter .12s}
.btn:hover{filter:brightness(1.15)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.btn.danger{background:var(--red-soft);border-color:transparent;color:var(--red)}
.btn.success{background:var(--green-soft);border-color:transparent;color:var(--green)}
.btn.sm{padding:3px 8px;font-size:11px}
.btn-row{display:flex;gap:4px}
.muted{color:var(--text-3)}
input,select,textarea{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:8px 10px;border-radius:var(--radius-sm);font-size:13px;font-family:inherit}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent)}
.filters{display:flex;gap:8px;margin-bottom:14px;align-items:end;flex-wrap:wrap;background:var(--surface);padding:12px;border-radius:var(--radius);border:1px solid var(--border)}
.filters label{font-size:11px;color:var(--text-2);display:flex;flex-direction:column;gap:4px}
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:99px;font-size:11px;font-weight:600}
.amt{font-weight:700;text-align:right;white-space:nowrap}
.amt.gasto{color:var(--red)}.amt.ingreso{color:var(--green)}
.dt{font-size:11px;color:var(--text-3);white-space:nowrap}
.dt b{font-size:13px;color:var(--text);font-weight:600;display:block}
.empty{text-align:center;padding:36px 20px;color:var(--text-3)}
.empty .ico{font-size:44px;margin-bottom:10px;opacity:.35}
.empty .cta{margin-top:14px}
.note{background:var(--surface-2);padding:12px 14px;border-radius:var(--radius-sm);margin-bottom:10px;border-left:3px solid var(--accent)}
.note .m{font-size:11px;color:var(--text-2);margin-bottom:6px}
.ev{display:flex;align-items:center;gap:14px;padding:10px 0;border-bottom:1px solid var(--border)}
.ev .d{font-size:11px;text-align:center;min-width:50px;color:var(--text-2)}
.ev .d .day{font-size:22px;font-weight:700;color:var(--text)}
.ev .b{flex:1}.ev .b .t{font-weight:600}.ev .b .m{font-size:12px;color:var(--text-2);margin-top:2px}
.account-card{padding:14px;border-radius:var(--radius);background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--accent);display:flex;flex-direction:column;gap:6px}
.account-card .name{font-weight:700;display:flex;align-items:center;gap:6px;justify-content:space-between;font-size:13px}
.account-card .bal{font-size:14px;color:var(--text-2)}
.account-card .bal.neg{color:var(--red)}.account-card .bal.pos{color:var(--green)}
.account-card .type{font-size:10px;color:var(--text-3);text-transform:uppercase}
.account-card .cuotas{margin-top:6px;padding-top:8px;border-top:1px dashed var(--border);font-size:11px;color:var(--text-2)}
.rate-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.rate{padding:12px;background:var(--surface-2);border-radius:var(--radius-sm);text-align:center}
.rate .t{font-size:10px;color:var(--text-2);text-transform:uppercase;letter-spacing:.5px}
.rate .v{font-size:18px;font-weight:700;margin-top:4px}
.priority-alta{color:var(--red)}.priority-media{color:var(--amber)}.priority-baja{color:var(--green)}
.chart-wrap{position:relative;height:270px}
.tag{display:inline-block;background:var(--surface-2);padding:2px 8px;border-radius:99px;font-size:11px;margin-right:4px}
.tx-actions{opacity:0;transition:opacity .15s}
tr:hover .tx-actions{opacity:1}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.65);display:flex;align-items:center;justify-content:center;z-index:200;padding:20px;backdrop-filter:blur(2px)}
.modal-content{background:var(--surface);border:1px solid var(--border);padding:22px;border-radius:var(--radius);max-width:500px;width:100%;max-height:90vh;overflow-y:auto}
.modal-content h3{margin:0 0 16px;font-size:16px}
.modal-content .field{display:flex;flex-direction:column;gap:4px;margin-bottom:12px}
.modal-content .field label{font-size:11px;color:var(--text-2)}
.modal-content .field input,.modal-content .field select,.modal-content .field textarea{width:100%}
.modal-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px;flex-wrap:wrap}
.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
#toast-container{position:fixed;top:64px;right:20px;z-index:300;display:flex;flex-direction:column;gap:8px;max-width:340px}
.toast{background:var(--surface);color:var(--text);padding:12px 16px;border-radius:var(--radius-sm);border:1px solid var(--border);border-left:4px solid var(--accent);box-shadow:var(--shadow);font-size:13px;animation:slideIn .25s ease}
.toast.success{border-left-color:var(--green)}.toast.error{border-left-color:var(--red)}
@keyframes slideIn{from{transform:translateX(20px);opacity:0}to{transform:translateX(0);opacity:1}}
.fab{position:fixed;bottom:78px;right:20px;width:54px;height:54px;border-radius:17px;background:linear-gradient(135deg,var(--accent),#9b6cff);color:#fff;border:none;font-size:24px;cursor:pointer;box-shadow:0 10px 26px rgba(108,140,255,.4);z-index:55;transition:transform .14s}
.fab:hover{transform:scale(1.07)}
@media(min-width:900px){.fab{bottom:28px}}
.bulk-bar{background:var(--accent);color:#fff;padding:10px 14px;border-radius:var(--radius-sm);margin-bottom:12px;display:none;align-items:center;gap:10px;flex-wrap:wrap}
.bulk-bar.show{display:flex}
.bulk-bar span{font-size:13px;font-weight:600;margin-right:auto}
.tx-cb{cursor:pointer}
.cuota-tag{display:inline-block;background:rgba(124,58,237,.2);color:#a78bfa;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:6px}
.color-swatch{width:20px;height:20px;border-radius:4px;display:inline-block;vertical-align:middle;border:1px solid var(--border)}
.palette-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(3px);display:none;align-items:flex-start;justify-content:center;padding-top:13vh;z-index:400}
.palette-overlay.open{display:flex}
.palette{width:520px;max-width:92vw;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden}
.palette input{width:100%;border:none;outline:none;background:transparent;color:var(--text);font-size:15px;padding:15px 18px;border-bottom:1px solid var(--border);border-radius:0}
.palette .opt{display:flex;gap:10px;align-items:center;padding:10px 18px;cursor:pointer;font-size:13.5px;color:var(--text-2)}
.palette .opt:hover,.palette .opt.sel{background:var(--surface-2);color:var(--text)}
</style></head><body>

<header><h1 id="page-title">🤖 Asistente</h1>
<div class="topbar-actions">
  <button class="btn" onclick="openPalette()" title="Buscar y crear">🔍 <span class="kbd-lbl">Ctrl+K</span></button>
  <button class="btn" id="theme-btn" onclick="toggleTheme()">☀️</button>
</div>
</header>
<aside class="sidebar" id="sidebar"></aside>
<div class="nav-bottom" id="nav-bottom"></div>

<main>
<section id="overview" class="section active">
<div class="hero">
  <div class="l">PATRIMONIO TOTAL · consolidado al blue</div>
  <div class="big" id="hero-patrimonio">—</div>
  <div class="s muted" id="hero-sub"></div>
</div>
<div class="kpi-row" id="kpi-row"></div>
<div class="gridB">
  <div class="panel"><div class="panel-head"><h2>📊 Cashflow — últimos 6 meses</h2></div><div class="chart-wrap"><canvas id="cf-chart"></canvas></div></div>
  <div class="panel"><div class="panel-head"><h2 id="hoy-title">☀️ Hoy</h2></div><div id="hoy-list"></div></div>
</div>
<div class="grid2" style="margin-bottom:16px">
  <div class="panel"><div class="panel-head"><h2>🎯 Presupuestos del mes</h2><button class="btn sm" onclick="switchTab('presupuestos')">Ver todos</button></div><div id="ov-budgets"></div></div>
  <div class="panel"><div class="panel-head"><h2 id="ov-cat-title">Por categoría</h2></div><div class="chart-wrap"><canvas id="cat-chart"></canvas></div></div>
</div>
<div class="panel"><h2>Cuentas y tarjetas</h2><div class="cards" id="acc-cards"></div></div>
</section>

<section id="transacciones" class="section">
<div class="filters">
  <label>Año <input type="number" id="t-year" style="width:80px"></label>
  <label>Mes <select id="t-month"></select></label>
  <label>Cuenta <select id="t-account"><option value="">Todas</option></select></label>
  <label>Categoría <select id="t-category"><option value="">Todas</option></select></label>
  <label>Tipo <select id="t-type"><option value="">Todos</option><option value="gasto">Gasto</option><option value="ingreso">Ingreso</option></select></label>
  <label>Moneda <select id="t-currency"><option value="">Todas</option><option value="ARS">ARS</option><option value="USD">USD</option><option value="EUR">EUR</option></select></label>
  <label>Buscar <input type="text" id="t-q" placeholder="descripción..."></label>
  <button class="btn primary" onclick="loadTx()">Aplicar</button>
  <button class="btn" onclick="resetTxFilters()">Reset</button>
  <button class="btn" onclick="exportCSV()">📥 CSV</button>
</div>
<div class="bulk-bar" id="bulk-bar"><span><span id="bulk-count">0</span> seleccionadas</span>
  <button class="btn sm" onclick="bulkMove()">Mover</button>
  <button class="btn sm danger" onclick="bulkDelete()">Borrar</button>
  <button class="btn sm" onclick="clearSel()">Cancelar</button>
</div>
<div class="panel">
  <div id="t-sums" style="margin-bottom:14px"></div>
  <div style="overflow-x:auto"><table id="tx-table"></table></div>
</div>
</section>

<section id="presupuestos" class="section">
<div class="filters"><button class="btn primary" onclick="modalBudget()">+ Nuevo presupuesto</button>
<span class="muted" style="font-size:12px;align-self:center">Límite mensual por categoría (ARS). El avance se reinicia cada mes.</span></div>
<div class="panel"><div id="bud-list"></div></div>
</section>

<section id="recurrentes" class="section">
<div class="filters">
  <label><input type="checkbox" id="rec-incl-inactive"> Mostrar pausadas</label>
  <button class="btn" onclick="loadRec()">Refrescar</button>
  <button class="btn primary" onclick="modalRecurrente()">+ Nueva</button>
</div>
<div class="panel"><div id="rec-list"></div></div>
</section>

<section id="cuentas" class="section">
<div class="filters">
  <label><input type="checkbox" id="acc-incl-inactive"> Mostrar archivadas</label>
  <button class="btn primary" onclick="modalAccount()">+ Nueva cuenta</button>
</div>
<div class="panel"><div id="acc-table"></div></div>
</section>

<section id="categorias" class="section">
<div class="filters">
  <label><input type="checkbox" id="cat-incl-inactive"> Mostrar archivadas</label>
  <button class="btn primary" onclick="modalCategory()">+ Nueva categoría</button>
</div>
<div class="panel"><div id="cat-table"></div></div>
</section>

<section id="cotizacion" class="section">
<div class="panel"><h2>Cotización del dólar</h2><div class="rate-grid" id="cot-grid"></div>
<p class="muted" style="margin-top:14px;font-size:12px">Fuente: dolarapi.com</p></div>
</section>

<section id="eventos" class="section">
<div class="filters"><button class="btn primary" onclick="modalEvento()">+ Nuevo evento</button></div>
<div class="panel"><h2>Próximos</h2><div id="ev-next"></div></div>
<div class="panel"><h2>Pasados</h2><div id="ev-past"></div></div>
</section>

<section id="tareas" class="section">
<div class="filters">
  <label><input type="radio" name="t-st" value="pendiente" checked> Pendientes</label>
  <label><input type="radio" name="t-st" value="hecha"> Hechas</label>
  <button class="btn primary" onclick="modalTarea()">+ Nueva</button>
</div>
<div class="panel"><div id="tareas-list"></div></div>
</section>

<section id="habitos" class="section">
<div class="filters"><label>Últimos <input type="number" id="h-days" value="30" style="width:60px"> días</label>
<button class="btn" onclick="loadHabitos()">Aplicar</button>
<button class="btn primary" onclick="modalHabito()">+ Registrar</button></div>
<div class="panel"><h2>Constancia — últimos 6 meses</h2><div id="h-heat"></div></div>
<div class="panel"><h2>Resumen</h2><div id="h-res"></div></div>
<div class="panel"><h2>Registros</h2><div style="overflow-x:auto"><table id="h-log"></table></div></div>
</section>

<section id="recordatorios" class="section">
<div class="filters"><label><input type="checkbox" id="rec-incl-fired"> Incluir disparados</label>
<button class="btn" onclick="loadRecs()">Refrescar</button>
<button class="btn primary" onclick="modalRecordatorio()">+ Nuevo</button></div>
<div class="panel"><h2>Recordatorios</h2><div id="rec-pend"></div></div>
</section>

<section id="notas" class="section">
<div class="filters"><input type="text" id="n-search" placeholder="Buscar..." style="flex:1">
<button class="btn" onclick="loadNotas()">Buscar</button>
<button class="btn primary" onclick="modalNota()">+ Nueva</button></div>
<div id="notas-list"></div>
</section>

</main>

<div class="palette-overlay" id="palette">
  <div class="palette">
    <input id="pal-input" placeholder="Buscar sección o crear: 'nueva transacción', 'tarea'…" autocomplete="off">
    <div id="pal-opts"></div>
  </div>
</div>

<button class="fab" onclick="modalTx()" title="Nueva transacción">+</button>
<div id="toast-container"></div>

<script>
const MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
const DIAS = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'];
let ACCOUNTS = [], CATEGORIES = [], SELECTED = new Set();

const NAV = [
  ["Finanzas", [
    ["overview","🏠","Inicio"], ["transacciones","💸","Transacciones"], ["presupuestos","🎯","Presupuestos"],
    ["recurrentes","🔁","Recurrentes"], ["cuentas","💳","Cuentas"], ["categorias","🏷️","Categorías"], ["cotizacion","💱","Cotización"]
  ]],
  ["Personal", [
    ["eventos","📅","Agenda"], ["tareas","✅","Tareas"], ["habitos","💪","Hábitos"],
    ["recordatorios","⏰","Recordatorios"], ["notas","📓","Notas"]
  ]],
];
const NAV_LABELS = {};
let CURRENT_TAB = 'overview';
const sb = document.getElementById('sidebar');
NAV.forEach(([group, items]) => {
  const lbl = document.createElement('div'); lbl.className = 'nav-label'; lbl.textContent = group; sb.appendChild(lbl);
  items.forEach(([id, ico, name]) => {
    NAV_LABELS[id] = `${ico} ${name}`;
    const b = document.createElement('button'); b.className = 'nav-item'; b.dataset.tab = id;
    b.innerHTML = `${ico} ${name}`;
    if (id === 'overview') b.classList.add('active');
    b.onclick = () => switchTab(id);
    sb.appendChild(b);
  });
});
const navBot = document.getElementById('nav-bottom');
[["overview","🏠","Inicio"],["transacciones","💸","Movs"],["presupuestos","🎯","Metas"],["tareas","✅","Tareas"]].forEach(([id,ico,lbl],i)=>{
  const b = document.createElement('button'); b.dataset.tab = id;
  b.innerHTML = `<span class="ico">${ico}</span>${lbl}`;
  if (i===0) b.classList.add('active');
  b.onclick = () => switchTab(id);
  navBot.appendChild(b);
});
const more = document.createElement('button');
more.innerHTML = '<span class="ico">⋯</span>Más'; more.onclick = openPalette;
navBot.appendChild(more);

function switchTab(id) {
  CURRENT_TAB = id;
  document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === id));
  document.querySelectorAll('.section').forEach(s => s.classList.toggle('active', s.id === id));
  document.getElementById('page-title').textContent = NAV_LABELS[id] || '🤖 Asistente';
  loadTab(id);
}

// ===== Tema claro/oscuro =====
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  document.getElementById('theme-btn').textContent = t === 'dark' ? '☀️' : '🌙';
  try { localStorage.setItem('theme', t); } catch(e) {}
}
function toggleTheme() {
  const t = (document.documentElement.dataset.theme === 'light') ? 'dark' : 'light';
  applyTheme(t); loadTab(CURRENT_TAB); // re-render charts con los colores nuevos
}
applyTheme((function(){ try { return localStorage.getItem('theme') || 'dark'; } catch(e) { return 'dark'; } })());
function cssv(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }

// ===== Command palette (Ctrl+K) =====
const PAL_OPTS = [];
NAV.forEach(([g, items]) => items.forEach(([id, ico, name]) => PAL_OPTS.push({label:`${ico} Ir a ${name}`, kw:name.toLowerCase(), fn:()=>switchTab(id)})));
[['💸 Nueva transacción','nueva transaccion gasto',()=>{switchTab('transacciones'); modalTx();}],
 ['✅ Nueva tarea','nueva tarea',()=>{switchTab('tareas'); modalTarea();}],
 ['⏰ Nuevo recordatorio','nuevo recordatorio',()=>{switchTab('recordatorios'); modalRecordatorio();}],
 ['📅 Nuevo evento','nuevo evento',()=>{switchTab('eventos'); modalEvento();}],
 ['🔁 Nueva recurrente','nueva recurrente cuota',()=>{switchTab('recurrentes'); modalRecurrente();}],
 ['🎯 Nuevo presupuesto','nuevo presupuesto',()=>{switchTab('presupuestos'); modalBudget();}],
 ['💪 Registrar hábito','registrar habito',()=>{switchTab('habitos'); modalHabito();}],
 ['📓 Nueva nota','nueva nota',()=>{switchTab('notas'); modalNota();}],
].forEach(([label,kw,fn])=>PAL_OPTS.push({label,kw,fn}));

const palEl = document.getElementById('palette'), palIn = document.getElementById('pal-input'), palOut = document.getElementById('pal-opts');
function renderPal() {
  const q = palIn.value.trim().toLowerCase();
  const hits = PAL_OPTS.filter(o => !q || o.label.toLowerCase().includes(q) || o.kw.includes(q)).slice(0, 9);
  palOut.innerHTML = hits.map((o,i)=>`<div class="opt${i===0?' sel':''}" data-i="${PAL_OPTS.indexOf(o)}">${o.label}</div>`).join('') || '<div class="opt muted">Sin resultados</div>';
  palOut.querySelectorAll('.opt[data-i]').forEach(el => el.onclick = () => { closePalette(); PAL_OPTS[+el.dataset.i].fn(); });
}
function openPalette(){ palEl.classList.add('open'); palIn.value=''; renderPal(); setTimeout(()=>palIn.focus(),30); }
function closePalette(){ palEl.classList.remove('open'); }
palEl.onclick = e => { if (e.target === palEl) closePalette(); };
palIn.oninput = renderPal;
palIn.onkeydown = e => {
  if (e.key === 'Enter') { const f = palOut.querySelector('.opt[data-i]'); if (f) { closePalette(); PAL_OPTS[+f.dataset.i].fn(); } }
  if (e.key === 'Escape') closePalette();
};
document.addEventListener('keydown', e => {
  if ((e.ctrlKey||e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); }
});

const tMon = document.getElementById('t-month');
const today = new Date();
['Todos', ...MESES].forEach((m, i) => {
  const o = document.createElement('option'); o.value = i === 0 ? '' : i; o.textContent = m;
  if (i === today.getMonth() + 1) o.selected = true; tMon.appendChild(o);
});
document.getElementById('t-year').value = today.getFullYear();
document.getElementById('rec-incl-inactive').onchange = loadRec;
document.getElementById('acc-incl-inactive').onchange = loadAccTable;
document.getElementById('cat-incl-inactive').onchange = loadCatTable;
document.getElementById('rec-incl-fired').onchange = loadRecs;

function parseDT(s){ return new Date((s||'').replace(' ','T')) }
function fmtMoney(n){ return Number(n||0).toLocaleString('es-AR',{minimumFractionDigits:2,maximumFractionDigits:2}) }
function esc(s){ return (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])) }
function fmtDay(d){ return String(d.getDate()).padStart(2,'0')+' '+MESES[d.getMonth()] }
function fmtTime(d){ return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0') }
async function api(p, o={}){
  if (o.body && typeof o.body === 'object') { o.body = JSON.stringify(o.body); o.headers = {...(o.headers||{}), 'Content-Type':'application/json'}; }
  const r = await fetch(p, o);
  if (!r.ok) { const e = await r.text().catch(()=>'Error'); throw new Error(e); }
  return r.json();
}
function toast(text, type='info') {
  const t = document.createElement('div'); t.className = `toast ${type}`; t.textContent = text;
  document.getElementById('toast-container').appendChild(t);
  setTimeout(()=>{ t.style.transition='opacity .3s'; t.style.opacity='0'; setTimeout(()=>t.remove(),300); }, 3000);
}

let LAST_TRASH = null;
async function softDelete(entity, id, label, reload) {
  const r = await api(`/api/trash/${entity}/${id}`, {method:'POST'});
  LAST_TRASH = {id: r.trash_id, reload};
  const t = document.createElement('div'); t.className = 'toast';
  t.innerHTML = `🗑 ${label} <button class="btn sm primary" style="margin-left:8px" onclick="undoDelete(this)">Deshacer</button>`;
  document.getElementById('toast-container').appendChild(t);
  setTimeout(()=>{ t.style.transition='opacity .3s'; t.style.opacity='0'; setTimeout(()=>t.remove(),300); }, 6000);
  reload();
}
async function undoDelete(btn) {
  if (!LAST_TRASH) return;
  const lt = LAST_TRASH; LAST_TRASH = null;
  await api(`/api/trash/restore/${lt.id}`, {method:'POST'});
  toast('Restaurado ↩','success'); lt.reload();
  btn.closest('.toast').remove();
}

function showModal(html, onSave) {
  const m = document.createElement('div'); m.className = 'modal';
  m.innerHTML = `<div class="modal-content">${html}<div class="modal-actions"><button class="btn" onclick="this.closest('.modal').remove()">Cancelar</button><button class="btn primary" id="modal-save">Guardar</button></div></div>`;
  m.onclick = e => { if (e.target === m) m.remove(); };
  document.body.appendChild(m);
  document.getElementById('modal-save').onclick = async () => {
    try { if (await onSave(m) !== false) m.remove(); }
    catch (e) { toast(e.message || 'Error', 'error'); }
  };
  setTimeout(() => { const f = m.querySelector('input, select, textarea'); if (f) f.focus(); }, 50);
  return m;
}

async function loadMeta(force = false) {
  if (!force && ACCOUNTS.length) return;
  ACCOUNTS = await api('/api/accounts');
  CATEGORIES = await api('/api/categories');
  const accSel = document.getElementById('t-account');
  accSel.innerHTML = '<option value="">Todas</option>';
  ACCOUNTS.forEach(a => { const o=document.createElement('option'); o.value=a.id; o.textContent=`${a.icon||''} ${a.name}`; accSel.appendChild(o); });
  const catSel = document.getElementById('t-category');
  catSel.innerHTML = '<option value="">Todas</option>';
  CATEGORIES.forEach(c => { const o=document.createElement('option'); o.value=c.id; o.textContent=`${c.icon||''} ${c.name}`; catSel.appendChild(o); });
  const oN = document.createElement('option'); oN.value=-1; oN.textContent='(sin categoría)'; catSel.appendChild(oN);
}

// ===== Overview v2 =====
let cfChart, catChart;
function budgetBar(b, actions) {
  const pct = b.amount ? Math.min(100, Math.round(b.spent / b.amount * 100)) : 0;
  const cls = pct >= 100 ? 'over' : (pct >= 80 ? 'warn' : '');
  const extra = actions ? `<span class="btn-row"><button class="btn sm" onclick='modalBudget(${JSON.stringify(b).replace(/'/g,"&apos;")})'>✏️</button><button class="btn sm danger" onclick="delBudget(${b.id})">×</button></span>` : '';
  return `<div class="brow"><div class="btop"><span>${b.icon||''} ${esc(b.name)}</span><span class="muted">$ ${fmtMoney(b.spent)} / ${fmtMoney(b.amount)} · ${pct}%${pct>=100?' ⚠':''} ${extra}</span></div><div class="bbar"><i class="${cls}" style="width:${pct}%"></i></div></div>`;
}
async function loadOverview(){
  await loadMeta();
  const [d, budgets, old] = await Promise.all([api('/api/overview2'), api('/api/budgets').catch(()=>[]), api('/api/overview')]);
  document.getElementById('hero-patrimonio').textContent = '$ ' + fmtMoney(d.patrimonio_ars);
  document.getElementById('hero-sub').textContent =
    (d.patrimonio_usd ? '≈ USD ' + fmtMoney(d.patrimonio_usd) + '  ·  ' : '') + (d.blue ? 'blue $' + fmtMoney(d.blue) : '');
  const k = d.kpis;
  const delta = k.gasto_prev_alt > 0 ? Math.round((k.gasto_mes - k.gasto_prev_alt) / k.gasto_prev_alt * 100) : null;
  const deltaH = delta === null ? '<span class="muted">sin datos del mes pasado</span>'
    : (delta <= 0 ? `<span class="pos">▼ ${-delta}%</span>` : `<span class="neg">▲ ${delta}%</span>`) + ` vs ${d.mes_nombre==='enero'?'dic':'mes pasado'} al día ${d.dia}`;
  document.getElementById('kpi-row').innerHTML = `
    <div class="kpi"><div class="l">💸 Gastado en ${d.mes_nombre}</div><div class="v">$ ${fmtMoney(k.gasto_mes)}</div><div class="s">${deltaH}</div></div>
    <div class="kpi"><div class="l">💰 Ingresos del mes</div><div class="v">$ ${fmtMoney(k.ingreso_mes)}</div><div class="s">sin transferencias</div></div>
    <div class="kpi"><div class="l">💳 Deuda tarjetas</div><div class="v neg">$ ${fmtMoney(k.deuda_tarjetas)}</div><div class="s">${k.cuotas_n} cuotas por venir · $ ${fmtMoney(k.cuotas_futuras)}</div></div>
    <div class="kpi"><div class="l">✨ Disponible</div><div class="v pos">$ ${fmtMoney(k.disponible)}</div><div class="s">efectivo + billeteras</div></div>`;
  const icons = {evento:'📅', recordatorio:'⏰', tarea:'✅', recurrente:'🔁'};
  document.getElementById('hoy-list').innerHTML = d.hoy.length
    ? d.hoy.map(h=>`<div class="today-item"><div class="t-ico">${icons[h.tipo]||'•'}</div><div><div class="t-t">${esc(h.titulo)}</div><div class="t-s">${esc(h.sub)}</div></div><div class="t-time">${esc(h.hora)}</div></div>`).join('')
    : '<div class="empty">Nada para hoy 🎉</div>';
  document.getElementById('ov-budgets').innerHTML = budgets.length
    ? budgets.slice(0,5).map(b=>budgetBar(b,false)).join('')
    : `<div class="empty">Sin presupuestos<div class="cta"><button class="btn primary" onclick="switchTab('presupuestos')">Crear el primero</button></div></div>`;
  // cashflow
  if (cfChart) cfChart.destroy();
  const ML = {'01':'Ene','02':'Feb','03':'Mar','04':'Abr','05':'May','06':'Jun','07':'Jul','08':'Ago','09':'Sep','10':'Oct','11':'Nov','12':'Dic'};
  cfChart = new Chart(document.getElementById('cf-chart'), {
    type: 'bar',
    data: { labels: d.cashflow.map(c=>ML[c.ym.slice(5)]||c.ym),
      datasets: [
        {label:'Ingresos', data:d.cashflow.map(c=>Math.round(c.ingresos)), backgroundColor:cssv('--green'), borderRadius:6, barPercentage:.55},
        {label:'Gastos', data:d.cashflow.map(c=>Math.round(c.gastos)), backgroundColor:cssv('--red'), borderRadius:6, barPercentage:.55}
      ]},
    options: { maintainAspectRatio:false,
      plugins:{legend:{position:'top',align:'end',labels:{color:cssv('--text-2'),boxWidth:10,boxHeight:10,usePointStyle:true}}},
      scales:{x:{grid:{display:false},ticks:{color:cssv('--text-2')}},
              y:{grid:{color:cssv('--border')},ticks:{color:cssv('--text-2'),callback:v=>'$'+(v>=1000000?(v/1000000).toFixed(1)+'M':(v/1000).toFixed(0)+'k')}}}}
  });
  // donut por categoría
  document.getElementById('ov-cat-title').textContent = `Por categoría — ${d.mes_nombre} ${d.year}`;
  if (catChart) catChart.destroy();
  const palette = ['#6c8cff','#fbbf24','#f87171','#34d399','#9b6cff','#38bdf8','#f472b6','#94a3b8'];
  if (d.por_categoria.length) catChart = new Chart(document.getElementById('cat-chart'), {
    type:'doughnut',
    data:{labels:d.por_categoria.map(p=>p.cat), datasets:[{data:d.por_categoria.map(p=>p.total), backgroundColor:d.por_categoria.map((p,i)=>p.color||palette[i%palette.length]), borderWidth:0, spacing:2, borderRadius:4}]},
    options:{cutout:'66%', maintainAspectRatio:false, plugins:{legend:{position:'right',labels:{color:cssv('--text-2'),boxWidth:9,boxHeight:9,usePointStyle:true,font:{size:11}}}}}
  });
  // cuentas (con cuotas de tarjetas)
  document.getElementById('acc-cards').innerHTML = old.accounts.map(a => {
    const bals = (a.balances||[]).map(b => `<div class="bal ${b.balance<0?'neg':'pos'}">${b.currency}: ${fmtMoney(b.balance)}</div>`).join('') || '<div class="muted">Sin movimientos</div>';
    const cuotas = (a.pending_cuotas||[]).filter(c=>c.remaining).length ? `<div class="cuotas">📅 ${(a.pending_cuotas||[]).filter(c=>c.remaining).map(c=>`${c.remaining}× ${fmtMoney(c.amount)} (${esc(c.description)})`).join('<br>')}</div>` : '';
    return `<div class="account-card" style="border-left-color:${a.color||'#6c8cff'}"><div class="name">${a.icon||''} ${esc(a.name)} <span class="type">${a.type}</span></div>${bals}${cuotas}</div>`;
  }).join('');
}

// ===== Transactions =====
function resetTxFilters(){ ['t-account','t-category','t-type','t-currency','t-q'].forEach(id=>document.getElementById(id).value=''); loadTx(); }
function exportCSV(){ const y=document.getElementById('t-year').value, m=document.getElementById('t-month').value; const u=y&&m?`/api/export.csv?year=${y}&month=${m}`:'/api/export.csv'; window.open(u); }
async function loadTx(){
  await loadMeta();
  const p = new URLSearchParams();
  const y = document.getElementById('t-year').value, m = document.getElementById('t-month').value;
  if (y && m) { p.set('year',y); p.set('month',m); }
  ['t-account','t-category','t-type','t-currency'].forEach(id=>{ const v=document.getElementById(id).value; if(v) p.set(id.replace('t-','').replace('account','account_id').replace('category','category_id'), v); });
  const q = document.getElementById('t-q').value.trim(); if(q) p.set('q',q);
  p.set('limit',300);
  const d = await api('/api/transactions?'+p);
  const sums = d.sums||[];
  const gas = sums.filter(s=>s.type==='gasto'), ing = sums.filter(s=>s.type==='ingreso');
  let sumsH=''; if (gas.length||ing.length) { sumsH='<div style="display:flex;gap:18px;flex-wrap:wrap">';
    gas.forEach(g=>sumsH+=`<div><span class="muted">Gastos ${g.currency}</span> <span class="amt gasto">-${fmtMoney(g.total)}</span></div>`);
    ing.forEach(i=>sumsH+=`<div><span class="muted">Ingresos ${i.currency}</span> <span class="amt ingreso">+${fmtMoney(i.total)}</span></div>`);
    sumsH+='</div>'; }
  document.getElementById('t-sums').innerHTML = sumsH;
  const t = document.getElementById('tx-table');
  if (!d.items.length) { t.innerHTML = '<tr><td><div class="empty"><div class="ico">📭</div>Sin transacciones</div></td></tr>'; return; }
  let h = '<thead><tr><th><input type="checkbox" id="tx-all" onclick="toggleAll(this)"></th><th>Fecha</th><th>Descripción</th><th>Categoría</th><th>Cuenta</th><th style="text-align:right">Monto</th><th></th></tr></thead><tbody>';
  for (const x of d.items) {
    const dt = parseDT(x.occurred_at);
    const sign = x.type==='gasto' ? '-' : '+', cls = x.type==='gasto' ? 'gasto' : 'ingreso';
    const catB = x.cat_name ? `<span class="badge" style="background:${x.cat_color||'#1e293b'}33;color:${x.cat_color||'#e2e8f0'}">${x.cat_icon||''} ${esc(x.cat_name)}</span>` : '<span class="muted">—</span>';
    const accB = `<span class="badge" style="background:${x.acc_color||'#1e293b'}33;color:${x.acc_color||'#e2e8f0'}">${x.acc_icon||''} ${esc(x.acc_name)}</span>`;
    const cuota = x.recurring_id && x.rec_total ? `<span class="cuota-tag">🧾 cuota ${(x.rec_fired||0)}/${x.rec_total}</span>` : (x.recurring_id ? '<span class="cuota-tag">🔁 recur.</span>' : '');
    h += `<tr><td><input type="checkbox" class="tx-cb" data-id="${x.id}" onclick="toggleSel(${x.id})"></td><td class="dt"><b>${fmtDay(dt)}</b>${fmtTime(dt)}</td><td>${esc(x.description||'(sin descripción)')}${cuota}<div class="muted" style="font-size:10px">#${x.id}</div></td><td>${catB}</td><td>${accB}</td><td class="amt ${cls}">${sign}${fmtMoney(x.amount)} ${x.currency}</td><td><div class="tx-actions btn-row"><button class="btn sm" onclick="editTx(${x.id})">✏️</button><button class="btn sm danger" onclick="delTx(${x.id})">×</button></div></td></tr>`;
  }
  h += '</tbody>'; t.innerHTML = h;
}
function toggleAll(cb) { document.querySelectorAll('.tx-cb').forEach(x=>{x.checked=cb.checked; const id=parseInt(x.dataset.id); if(cb.checked)SELECTED.add(id); else SELECTED.delete(id);}); updateBulkBar(); }
function toggleSel(id) { if(SELECTED.has(id))SELECTED.delete(id); else SELECTED.add(id); updateBulkBar(); }
function updateBulkBar() { const b=document.getElementById('bulk-bar'); document.getElementById('bulk-count').textContent=SELECTED.size; b.classList.toggle('show', SELECTED.size>0); }
function clearSel() { SELECTED.clear(); document.querySelectorAll('.tx-cb').forEach(x=>x.checked=false); const a=document.getElementById('tx-all'); if(a)a.checked=false; updateBulkBar(); }
async function bulkDelete() { if (!confirm(`¿Borrar ${SELECTED.size} transacciones?`)) return;
  try { await api('/api/transactions/bulk_delete',{method:'POST',body:{ids:[...SELECTED]}}); toast('Borradas','success'); clearSel(); loadTx(); }
  catch(e){ toast('Error: '+e.message,'error'); }
}
function bulkMove() {
  const accOpts = ACCOUNTS.map(a=>`<option value="${a.id}">${a.icon||''} ${esc(a.name)}</option>`).join('');
  const catOpts = '<option value="">No cambiar</option>' + CATEGORIES.map(c=>`<option value="${c.id}">${c.icon||''} ${esc(c.name)}</option>`).join('');
  showModal(`<h3>Mover ${SELECTED.size} transacciones</h3>
    <div class="field"><label>Cuenta destino</label><select id="bm-acc"><option value="">No cambiar</option>${accOpts}</select></div>
    <div class="field"><label>Categoría destino</label><select id="bm-cat">${catOpts}</select></div>`,
    async () => {
      const body = {ids:[...SELECTED]};
      const a = document.getElementById('bm-acc').value, c = document.getElementById('bm-cat').value;
      if (a) body.account_id = parseInt(a); if (c) body.category_id = parseInt(c);
      if (!body.account_id && !body.category_id) { toast('Elegí algo a cambiar','error'); return false; }
      await api('/api/transactions/bulk_move',{method:'POST',body}); toast('Movidas','success'); clearSel(); loadTx();
    });
}
async function delTx(id) { softDelete('transactions', id, 'Transacción borrada', loadTx); }

function modalTx(tx=null) {
  const isEdit = tx !== null;
  const accOpts = ACCOUNTS.map(a=>`<option value="${a.id}" ${tx&&tx.account_id===a.id?'selected':''}>${a.icon||''} ${esc(a.name)}</option>`).join('');
  const catOpts = '<option value="">(sin categoría)</option>' + CATEGORIES.map(c=>`<option value="${c.id}" ${tx&&tx.category_id===c.id?'selected':''}>${c.icon||''} ${esc(c.name)}</option>`).join('');
  const nowISO = new Date().toISOString().slice(0,16);
  showModal(`<h3>${isEdit?'Editar':'Nueva'} transacción</h3>
    <div class="field-grid">
      <div class="field"><label>Tipo</label><select id="tx-type"><option value="gasto" ${tx&&tx.type==='gasto'?'selected':''}>Gasto</option><option value="ingreso" ${tx&&tx.type==='ingreso'?'selected':''}>Ingreso</option></select></div>
      <div class="field"><label>Monto</label><input type="number" id="tx-amount" step="0.01" value="${tx?tx.amount:''}"></div>
      <div class="field"><label>Moneda</label><select id="tx-currency"><option ${tx&&tx.currency==='ARS'?'selected':''}>ARS</option><option ${tx&&tx.currency==='USD'?'selected':''}>USD</option><option ${tx&&tx.currency==='EUR'?'selected':''}>EUR</option></select></div>
      <div class="field"><label>Cuenta</label><select id="tx-account">${accOpts}</select></div>
    </div>
    <div class="field"><label>Categoría</label><select id="tx-category">${catOpts}</select></div>
    <div class="field"><label>Descripción</label><input type="text" id="tx-desc" value="${tx?esc(tx.description||''):''}"></div>
    <div class="field"><label>Fecha y hora</label><input type="datetime-local" id="tx-when" value="${tx?(tx.occurred_at||'').slice(0,16):nowISO}"></div>`,
    async () => {
      const body = {
        type: document.getElementById('tx-type').value,
        amount: parseFloat(document.getElementById('tx-amount').value),
        currency: document.getElementById('tx-currency').value,
        account_id: parseInt(document.getElementById('tx-account').value),
        category_id: document.getElementById('tx-category').value ? parseInt(document.getElementById('tx-category').value) : null,
        description: document.getElementById('tx-desc').value,
        occurred_at: document.getElementById('tx-when').value,
      };
      if (!body.amount || !body.account_id) { toast('Faltan datos','error'); return false; }
      if (isEdit) { await api(`/api/transactions/${tx.id}`,{method:'PATCH',body}); toast('Actualizada','success'); }
      else { await api('/api/transactions',{method:'POST',body}); toast('Creada','success'); }
      loadTx();
    });
}
async function editTx(id) {
  const r = await fetch(`/api/transactions?limit=1&offset=0`); // fetch this one
  const tx = (await api('/api/transactions?limit=500')).items.find(x => x.id === id);
  if (!tx) { toast('No encontrada','error'); return; }
  modalTx(tx);
}

// ===== Recurrentes =====
async function loadRec() {
  await loadMeta();
  const incl = document.getElementById('rec-incl-inactive').checked;
  const arr = await api('/api/recurring?include_inactive='+incl);
  const el = document.getElementById('rec-list');
  if (!arr.length) { el.innerHTML = '<div class="empty"><div class="ico">🔁</div>Sin recurrentes</div>'; return; }
  let h = '<table><thead><tr><th>Descripción</th><th>Monto</th><th>Cuenta</th><th>Categoría</th><th>Cuota</th><th>Día</th><th>Próxima</th><th>Estado</th><th></th></tr></thead><tbody>';
  for (const r of arr) {
    const sign = r.type==='gasto' ? '-' : '+', cls = r.type==='gasto' ? 'gasto' : 'ingreso';
    const accB = `<span class="badge" style="background:${r.acc_color||'#1e293b'}33;color:${r.acc_color||'#e2e8f0'}">${r.acc_icon||''} ${esc(r.acc_name)}</span>`;
    const catB = r.cat_name ? `<span class="badge" style="background:${r.cat_color||'#1e293b'}33;color:${r.cat_color||'#e2e8f0'}">${r.cat_icon||''} ${esc(r.cat_name)}</span>` : '<span class="muted">—</span>';
    const cuotaInfo = r.total_installments ? `${(r.installments_fired||0)+1}/${r.total_installments}` : '∞';
    h += `<tr><td>${esc(r.description)}<div class="muted" style="font-size:10px">#${r.id}</div></td><td class="amt ${cls}">${sign}${fmtMoney(r.amount)} ${r.currency}</td><td>${accB}</td><td>${catB}</td><td>${cuotaInfo}</td><td>${r.day_of_month||'—'}</td><td>${r.next_occurrence}</td><td>${r.active?'<span style="color:#4ade80">● activa</span>':'<span class="muted">○ pausada</span>'}</td><td class="btn-row"><button class="btn sm" onclick="toggleRec(${r.id},${r.active?0:1})">${r.active?'Pausar':'Activar'}</button><button class="btn sm danger" onclick="delRecRow(${r.id})">×</button></td></tr>`;
  }
  h += '</tbody>'; el.innerHTML = h;
}
async function toggleRec(id, active) { await api(`/api/recurring/${id}`,{method:'PATCH',body:{active}}); toast(active?'Activada':'Pausada','success'); loadRec(); }
async function delRecRow(id) { softDelete('recurring', id, 'Recurrente borrada', loadRec); }

// ===== Cuentas CRUD =====
async function loadAccTable() {
  const incl = document.getElementById('acc-incl-inactive').checked;
  const arr = await api('/api/accounts?include_inactive='+incl);
  await loadMeta(true);
  const el = document.getElementById('acc-table');
  if (!arr.length) { el.innerHTML='<div class="empty"><div class="ico">💳</div>Sin cuentas<div class="cta"><button class="btn primary" onclick="modalAccount()">+ Crear primera</button></div></div>'; return; }
  let h = '<table><thead><tr><th>Color</th><th>Nombre</th><th>Tipo</th><th>Estado</th><th></th></tr></thead><tbody>';
  for (const a of arr) {
    h += `<tr><td><span class="color-swatch" style="background:${a.color||'#1e293b'}"></span> ${a.icon||''}</td><td>${esc(a.name)}</td><td><span class="muted">${a.type}</span></td><td>${a.active?'<span style="color:#4ade80">activa</span>':'<span class="muted">archivada</span>'}</td><td class="btn-row"><button class="btn sm" onclick='modalAccount(${JSON.stringify(a).replace(/'/g,"&apos;")})'>✏️</button><button class="btn sm danger" onclick="delAcc(${a.id})">×</button></td></tr>`;
  }
  h += '</tbody>'; el.innerHTML = h;
}
function modalAccount(acc=null) {
  const isEdit = acc !== null;
  const types = ['efectivo','billetera','credito','debito','inversion','transferencia'];
  showModal(`<h3>${isEdit?'Editar':'Nueva'} cuenta</h3>
    <div class="field"><label>Nombre</label><input type="text" id="acc-name" value="${acc?esc(acc.name):''}"></div>
    <div class="field-grid">
      <div class="field"><label>Tipo</label><select id="acc-type">${types.map(t=>`<option ${acc&&acc.type===t?'selected':''}>${t}</option>`).join('')}</select></div>
      <div class="field"><label>Icono (emoji)</label><input type="text" id="acc-icon" value="${acc?esc(acc.icon||''):'💳'}"></div>
    </div>
    <div class="field"><label>Color</label><input type="color" id="acc-color" value="${acc?acc.color||'#60a5fa':'#60a5fa'}"></div>
    ${isEdit?'<div class="field"><label><input type="checkbox" id="acc-active" '+(acc.active?'checked':'')+'> Activa</label></div>':''}`,
    async () => {
      const body = { name: document.getElementById('acc-name').value.trim(), type: document.getElementById('acc-type').value, icon: document.getElementById('acc-icon').value, color: document.getElementById('acc-color').value };
      if (isEdit) body.active = document.getElementById('acc-active').checked;
      if (!body.name) { toast('Nombre requerido','error'); return false; }
      if (isEdit) await api(`/api/accounts/${acc.id}`,{method:'PATCH',body});
      else await api('/api/accounts',{method:'POST',body});
      toast(isEdit?'Actualizada':'Creada','success'); loadAccTable();
    });
}
async function delAcc(id) { if (!confirm('¿Eliminar? Si tiene transacciones se archiva.')) return; const r=await api(`/api/accounts/${id}`,{method:'DELETE'}); toast(r.archived?'Archivada':'Borrada','success'); loadAccTable(); }

// ===== Categorías CRUD =====
async function loadCatTable() {
  const incl = document.getElementById('cat-incl-inactive').checked;
  const arr = await api('/api/categories?include_inactive='+incl);
  await loadMeta(true);
  const el = document.getElementById('cat-table');
  if (!arr.length) { el.innerHTML='<div class="empty"><div class="ico">🏷️</div>Sin categorías</div>'; return; }
  let h = '<table><thead><tr><th>Color</th><th>Nombre</th><th>Tipo</th><th>Estado</th><th></th></tr></thead><tbody>';
  for (const c of arr) {
    h += `<tr><td><span class="color-swatch" style="background:${c.color||'#1e293b'}"></span> ${c.icon||''}</td><td>${esc(c.name)}</td><td><span class="muted">${c.type}</span></td><td>${c.active?'<span style="color:#4ade80">activa</span>':'<span class="muted">archivada</span>'}</td><td class="btn-row"><button class="btn sm" onclick='modalCategory(${JSON.stringify(c).replace(/'/g,"&apos;")})'>✏️</button><button class="btn sm danger" onclick="delCat(${c.id})">×</button></td></tr>`;
  }
  h += '</tbody>'; el.innerHTML = h;
}
function modalCategory(cat=null) {
  const isEdit = cat !== null;
  showModal(`<h3>${isEdit?'Editar':'Nueva'} categoría</h3>
    <div class="field"><label>Nombre</label><input type="text" id="cat-name" value="${cat?esc(cat.name):''}"></div>
    <div class="field-grid">
      <div class="field"><label>Tipo</label><select id="cat-type"><option value="gasto" ${cat&&cat.type==='gasto'?'selected':''}>Gasto</option><option value="ingreso" ${cat&&cat.type==='ingreso'?'selected':''}>Ingreso</option></select></div>
      <div class="field"><label>Icono</label><input type="text" id="cat-icon" value="${cat?esc(cat.icon||''):'📦'}"></div>
    </div>
    <div class="field"><label>Color</label><input type="color" id="cat-color" value="${cat?cat.color||'#94a3b8':'#94a3b8'}"></div>
    ${isEdit?'<div class="field"><label><input type="checkbox" id="cat-active" '+(cat.active?'checked':'')+'> Activa</label></div>':''}`,
    async () => {
      const body = { name: document.getElementById('cat-name').value.trim(), type: document.getElementById('cat-type').value, icon: document.getElementById('cat-icon').value, color: document.getElementById('cat-color').value };
      if (isEdit) body.active = document.getElementById('cat-active').checked;
      if (!body.name) { toast('Nombre requerido','error'); return false; }
      if (isEdit) await api(`/api/categories/${cat.id}`,{method:'PATCH',body});
      else await api('/api/categories',{method:'POST',body});
      toast(isEdit?'Actualizada':'Creada','success'); loadCatTable();
    });
}
async function delCat(id) { if (!confirm('¿Eliminar? Si tiene transacciones se archiva.')) return; const r=await api(`/api/categories/${id}`,{method:'DELETE'}); toast(r.archived?'Archivada':'Borrada','success'); loadCatTable(); }

// ===== Cotización =====
async function loadCot() {
  const d = await api('/api/cotizacion');
  const types = [['oficial','Oficial'],['blue','Blue'],['mep','MEP'],['cripto','Cripto']];
  document.getElementById('cot-grid').innerHTML = types.map(([k,l])=>`<div class="rate"><div class="t">${l}</div><div class="v">${d[k]?'$'+fmtMoney(d[k]):'<span class="muted">N/D</span>'}</div></div>`).join('');
}

// ===== Eventos =====
async function loadEv() {
  const [nx, ps] = await Promise.all([api('/api/eventos'), api('/api/eventos?past=true')]);
  const r = (arr, id) => { const el=document.getElementById(id);
    if (!arr.length) { el.innerHTML='<div class="empty">Nada</div>'; return; }
    el.innerHTML = arr.map(e => { const d=parseDT(e.starts_at); return `<div class="ev"><div class="d"><div>${MESES[d.getMonth()]}</div><div class="day">${d.getDate()}</div><div>${fmtTime(d)}</div></div><div class="b"><div class="t">${esc(e.title)}</div><div class="m">${esc(e.location||'')}${e.notes?' · '+esc(e.notes):''}</div></div><button class="btn sm" onclick='modalEvento(${JSON.stringify(e).replace(/'/g,"&apos;")})'>✏️</button><button class="btn sm danger" onclick="delEv(${e.id})">×</button></div>`}).join(''); };
  r(nx, 'ev-next'); r(ps, 'ev-past');
}
async function delEv(id) { softDelete('eventos', id, 'Evento borrado', loadEv); }

// ===== Tareas =====
async function loadTar() {
  const st = document.querySelector('input[name=t-st]:checked').value;
  const arr = await api(`/api/tareas?status=${st}`);
  const el = document.getElementById('tareas-list');
  if (!arr.length) { el.innerHTML='<div class="empty"><div class="ico">✅</div>Sin tareas</div>'; return; }
  let h = '<table><thead><tr><th></th><th>Tarea</th><th>Prioridad</th><th>Vence</th><th></th></tr></thead><tbody>';
  for (const t of arr) {
    h += `<tr><td>${t.status==='pendiente'?`<button class="btn success sm" onclick="tDone(${t.id})">✓</button>`:`<button class="btn sm" onclick="tUndo(${t.id})">↩</button>`}</td><td>${esc(t.text)}<div class="muted" style="font-size:10px">#${t.id}</div></td><td class="priority-${t.priority}">${t.priority}</td><td>${t.due_at?esc(t.due_at):'<span class="muted">—</span>'}</td><td class="btn-row"><button class="btn sm" onclick='modalTarea(${JSON.stringify(t).replace(/'/g,"&apos;")})'>✏️</button><button class="btn sm danger" onclick="delTar(${t.id})">×</button></td></tr>`;
  }
  h += '</tbody>'; el.innerHTML = h;
}
function modalTarea(t=null) {
  const isEdit = t !== null;
  showModal(`<h3>${isEdit?'Editar':'Nueva'} tarea</h3>
    <div class="field"><label>Texto</label><textarea id="ta-text" rows="2">${t?esc(t.text):''}</textarea></div>
    <div class="field-grid">
      <div class="field"><label>Prioridad</label><select id="ta-pri"><option value="baja" ${t&&t.priority==='baja'?'selected':''}>Baja</option><option value="media" ${!t||t.priority==='media'?'selected':''}>Media</option><option value="alta" ${t&&t.priority==='alta'?'selected':''}>Alta</option></select></div>
      <div class="field"><label>Vence</label><input type="date" id="ta-due" value="${t&&t.due_at?String(t.due_at).slice(0,10):''}"></div>
    </div>`,
    async () => {
      const body = { text: document.getElementById('ta-text').value.trim(), priority: document.getElementById('ta-pri').value, due_at: document.getElementById('ta-due').value || null };
      if (!body.text) { toast('Texto requerido','error'); return false; }
      if (isEdit) { await api(`/api/tareas/${t.id}`,{method:'PATCH',body}); toast('Actualizada','success'); }
      else { await api('/api/tareas',{method:'POST',body}); toast('Creada','success'); }
      loadTar();
    });
}
async function tDone(id) { await api(`/api/tareas/${id}/done`,{method:'POST'}); toast('Hecha','success'); loadTar(); }
async function tUndo(id) { await api(`/api/tareas/${id}/undone`,{method:'POST'}); loadTar(); }
async function delTar(id) { softDelete('tareas', id, 'Tarea borrada', loadTar); }
document.querySelectorAll('input[name=t-st]').forEach(r=>r.onchange=loadTar);

// ===== Hábitos =====
function dkey(d){ return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
function calcStreak(daysMap){
  let cur=0, max=0, run=0;
  let d=new Date();
  while(daysMap[dkey(d)]){ cur++; d.setDate(d.getDate()-1); }
  d=new Date(); d.setDate(d.getDate()-181);
  for(let i=0;i<182;i++){ run=daysMap[dkey(d)]?run+1:0; if(run>max)max=run; d.setDate(d.getDate()+1); }
  return {cur,max};
}
async function loadHabitos() {
  const days = document.getElementById('h-days').value;
  const [d, hm] = await Promise.all([api(`/api/habitos?days=${days}`), api('/api/habitos?days=182')]);
  document.getElementById('h-res').innerHTML = d.resumen.length ?
    '<table><thead><tr><th>Hábito</th><th>Veces</th><th>Total</th></tr></thead><tbody>' +
    d.resumen.map(h=>`<tr><td>${esc(h.name)}</td><td>${h.cnt}</td><td>${h.total&&h.unit?h.total+' '+esc(h.unit):'<span class="muted">—</span>'}</td></tr>`).join('')+'</tbody>' :
    '<div class="empty">Sin registros</div>';
  document.getElementById('h-log').innerHTML = d.items.length ?
    '<thead><tr><th>Fecha</th><th>Hábito</th><th>Valor</th><th></th></tr></thead><tbody>' +
    d.items.map(h=>`<tr><td>${parseDT(h.logged_at).toLocaleString('es-AR')}</td><td>${esc(h.name)}</td><td>${h.value&&h.unit?h.value+' '+esc(h.unit):''}</td><td><button class="btn sm danger" onclick="delHabito(${h.id})">×</button></td></tr>`).join('')+'</tbody>' :
    '<thead><tr><th>Fecha</th><th>Hábito</th><th>Valor</th><th></th></tr></thead><tbody><tr><td colspan=4 class="empty">Sin registros</td></tr></tbody>';
  // heatmaps (top 3 hábitos del semestre)
  const byName = {};
  hm.items.forEach(it=>{ const day=(it.logged_at||'').slice(0,10); (byName[it.name]=byName[it.name]||{})[day]=(byName[it.name][day]||0)+1; });
  const tops = Object.entries(byName).sort((a,b)=>Object.keys(b[1]).length-Object.keys(a[1]).length).slice(0,3);
  document.getElementById('h-heat').innerHTML = tops.length ? tops.map(([name, daysMap])=>{
    const cells=[]; const start=new Date(); start.setDate(start.getDate()-181);
    const cur=new Date(start);
    for(let i=0;i<182;i++){ const k=dkey(cur); const n=daysMap[k]||0; const lvl=n===0?0:(n===1?2:4);
      cells.push(`<div class="hm-cell hm-${lvl}" title="${k}${n?' · '+n:''}"></div>`); cur.setDate(cur.getDate()+1); }
    const st=calcStreak(daysMap);
    return `<div class="hm-block"><div class="hm-head"><b>💪 ${esc(name)}</b><span class="muted">🔥 racha ${st.cur} días · récord ${st.max} · ${Object.keys(daysMap).length} días activos</span></div><div class="hm-grid">${cells.join('')}</div></div>`;
  }).join('') : '<div class="empty">Todavía sin datos — registrá tu primer hábito</div>';
}

// ===== Recordatorios =====
async function loadRecs() {
  const incl = document.getElementById('rec-incl-fired').checked;
  const arr = await api('/api/recordatorios?include_fired='+incl);
  const el = document.getElementById('rec-pend');
  if (!arr.length) { el.innerHTML='<div class="empty"><div class="ico">⏰</div>Sin recordatorios</div>'; return; }
  let h = '<table><thead><tr><th>Estado</th><th>Cuándo</th><th>Texto</th><th>Origen</th><th></th></tr></thead><tbody>';
  for (const r of arr) {
    const d = parseDT(r.remind_at);
    const status = r.fired ? '<span style="color:#4ade80">✓ disparado</span>' : '<span style="color:#fbbf24">⏳ pendiente</span>';
    h += `<tr><td>${status}</td><td class="dt"><b>${fmtDay(d)}</b>${fmtTime(d)}</td><td>${esc(r.text)}</td><td class="muted">${esc(r.source||'')}</td><td class="btn-row">${r.fired?'':`<button class="btn sm" onclick="snoozeRec(${r.id},'1h')">+1h</button><button class="btn sm" onclick="snoozeRec(${r.id},'manana')">Mañana</button>`}<button class="btn sm danger" onclick="delRecPend(${r.id})">×</button></td></tr>`;
  }
  h += '</tbody>'; el.innerHTML = h;
}
async function delRecPend(id) { softDelete('recordatorios', id, 'Recordatorio borrado', loadRecs); }

// ===== Notas =====
async function loadNotas() {
  const q = document.getElementById('n-search').value.trim();
  const arr = await api(`/api/notas${q?'?q='+encodeURIComponent(q):''}`);
  const el = document.getElementById('notas-list');
  if (!arr.length) { el.innerHTML='<div class="empty"><div class="ico">📓</div>Sin notas</div>'; return; }
  el.innerHTML = arr.map(n=>{ const tags=n.tags?JSON.parse(n.tags):[]; return `<div class="note"><div class="m">${parseDT(n.created_at).toLocaleString('es-AR')} · #${n.id}<button class="btn sm danger" style="float:right" onclick="delNotaItem(${n.id})">×</button><button class="btn sm" style="float:right;margin-right:4px" onclick='modalNota(${JSON.stringify(n).replace(/'/g,"&apos;")})'>✏️</button></div><div>${esc(n.text).replace(/\n/g,'<br>')}</div>${tags.length?'<div style="margin-top:8px">'+tags.map(t=>'<span class="tag">'+esc(t)+'</span>').join('')+'</div>':''}</div>`}).join('');
}
function modalNota(n=null) {
  const isEdit = n !== null;
  showModal(`<h3>${isEdit?'Editar':'Nueva'} nota</h3><div class="field"><label>Texto</label><textarea id="n-text" rows="5">${n?esc(n.text):''}</textarea></div>`,
    async () => {
      const text = document.getElementById('n-text').value.trim();
      if (!text) { toast('Texto requerido','error'); return false; }
      if (isEdit) { await api(`/api/notas/${n.id}`,{method:'PATCH',body:{text}}); toast('Actualizada','success'); }
      else { await api('/api/notas',{method:'POST',body:{text}}); toast('Creada','success'); }
      loadNotas();
    });
}
async function delNotaItem(id) { softDelete('notas', id, 'Nota borrada', loadNotas); }
document.getElementById('n-search').addEventListener('keydown', e => { if (e.key === 'Enter') loadNotas(); });


// ===== Nuevos modales (CRUD v2) =====
async function modalRecurrente() {
  await loadMeta();
  const accOpts = ACCOUNTS.map(a=>`<option value="${a.id}">${a.icon||''} ${esc(a.name)}</option>`).join('');
  const catOpts = '<option value="">(sin categoría)</option>' + CATEGORIES.map(c=>`<option value="${c.id}">${c.icon||''} ${esc(c.name)}</option>`).join('');
  showModal(`<h3>Nueva recurrente</h3>
    <div class="field"><label>Descripción</label><input type="text" id="rc-desc" placeholder="Movistar"></div>
    <div class="field-grid">
      <div class="field"><label>Tipo</label><select id="rc-type"><option value="gasto">Gasto</option><option value="ingreso">Ingreso</option></select></div>
      <div class="field"><label>Monto</label><input type="number" id="rc-amount" step="0.01"></div>
      <div class="field"><label>Moneda</label><select id="rc-currency"><option>ARS</option><option>USD</option><option>EUR</option></select></div>
      <div class="field"><label>Cuenta</label><select id="rc-account">${accOpts}</select></div>
      <div class="field"><label>Categoría</label><select id="rc-category">${catOpts}</select></div>
      <div class="field"><label>Día del mes (1-28)</label><input type="number" id="rc-day" min="1" max="28" value="10"></div>
    </div>
    <div class="field"><label>Cuotas (vacío = sin fin)</label><input type="number" id="rc-inst" min="1" placeholder="∞"></div>`,
    async () => {
      const body = {
        type: document.getElementById('rc-type').value,
        amount: parseFloat(document.getElementById('rc-amount').value),
        currency: document.getElementById('rc-currency').value,
        account_id: parseInt(document.getElementById('rc-account').value),
        category_id: document.getElementById('rc-category').value ? parseInt(document.getElementById('rc-category').value) : null,
        description: document.getElementById('rc-desc').value.trim(),
        day_of_month: parseInt(document.getElementById('rc-day').value),
        total_installments: document.getElementById('rc-inst').value ? parseInt(document.getElementById('rc-inst').value) : null,
      };
      if (!body.amount || !body.description || !body.day_of_month) { toast('Faltan datos','error'); return false; }
      await api('/api/recurring',{method:'POST',body}); toast('Creada','success'); loadRec();
    });
}
function modalEvento(ev=null) {
  const isEdit = ev !== null;
  showModal(`<h3>${isEdit?'Editar':'Nuevo'} evento</h3>
    <div class="field"><label>Título</label><input type="text" id="ev-title" value="${ev?esc(ev.title):''}"></div>
    <div class="field"><label>Fecha y hora</label><input type="datetime-local" id="ev-when" value="${ev?(ev.starts_at||'').replace(' ','T').slice(0,16):''}"></div>
    <div class="field"><label>Lugar</label><input type="text" id="ev-loc" value="${ev?esc(ev.location||''):''}"></div>
    <div class="field"><label>Notas</label><textarea id="ev-notes" rows="2">${ev?esc(ev.notes||''):''}</textarea></div>`,
    async () => {
      const body = {
        title: document.getElementById('ev-title').value.trim(),
        starts_at: document.getElementById('ev-when').value,
        location: document.getElementById('ev-loc').value || null,
        notes: document.getElementById('ev-notes').value || null,
      };
      if (!body.title || !body.starts_at) { toast('Faltan datos','error'); return false; }
      if (isEdit) { await api(`/api/eventos/${ev.id}`,{method:'PATCH',body}); toast('Actualizado','success'); }
      else { await api('/api/eventos',{method:'POST',body}); toast('Creado','success'); }
      loadEv();
    });
}
function modalRecordatorio() {
  showModal(`<h3>Nuevo recordatorio</h3>
    <div class="field"><label>Texto</label><input type="text" id="rm-text" placeholder="Pagar el internet"></div>
    <div class="field"><label>Cuándo</label><input type="datetime-local" id="rm-when"></div>
    <p class="muted" style="font-size:11px;margin:0">Te llega por Telegram (puede demorar hasta 1 min).</p>`,
    async () => {
      const body = { text: document.getElementById('rm-text').value.trim(), remind_at: document.getElementById('rm-when').value };
      if (!body.text || !body.remind_at) { toast('Faltan datos','error'); return false; }
      await api('/api/recordatorios',{method:'POST',body}); toast('Creado','success'); loadRecs();
    });
}
async function snoozeRec(id, preset) {
  await api(`/api/recordatorios/${id}/snooze?preset=${preset}`,{method:'POST'});
  toast(preset==='1h'?'Pospuesto 1 hora':'Pospuesto a mañana 9:00','success'); loadRecs();
}
function modalHabito() {
  showModal(`<h3>Registrar hábito</h3>
    <div class="field"><label>Hábito</label><input type="text" id="hb-name" placeholder="ejercicio"></div>
    <div class="field-grid">
      <div class="field"><label>Cantidad</label><input type="number" id="hb-value" step="0.1"></div>
      <div class="field"><label>Unidad</label><input type="text" id="hb-unit" placeholder="min"></div>
    </div>
    <div class="field"><label>Nota</label><input type="text" id="hb-note"></div>`,
    async () => {
      const body = {
        name: document.getElementById('hb-name').value.trim().toLowerCase(),
        value: document.getElementById('hb-value').value ? parseFloat(document.getElementById('hb-value').value) : null,
        unit: document.getElementById('hb-unit').value || null,
        note: document.getElementById('hb-note').value || null,
      };
      if (!body.name) { toast('Nombre requerido','error'); return false; }
      await api('/api/habitos',{method:'POST',body}); toast('Registrado','success'); loadHabitos();
    });
}
async function delHabito(id) { softDelete('habitos', id, 'Registro borrado', loadHabitos); }

// ===== Presupuestos =====
async function loadBudgets() {
  await loadMeta();
  const arr = await api('/api/budgets');
  const el = document.getElementById('bud-list');
  if (!arr.length) { el.innerHTML = `<div class="empty"><div class="ico">🎯</div>Sin presupuestos<div class="cta"><button class="btn primary" onclick="modalBudget()">+ Crear el primero</button></div></div>`; return; }
  const tot = arr.reduce((s,b)=>s+b.amount,0), spent = arr.reduce((s,b)=>s+b.spent,0);
  el.innerHTML = `<div class="muted" style="margin-bottom:14px">Total: $ ${fmtMoney(spent)} de $ ${fmtMoney(tot)} (${Math.round(spent/tot*100)}%)</div>` +
    arr.map(b=>budgetBar(b,true)).join('');
}
function modalBudget(b=null) {
  const isEdit = b !== null;
  const catOpts = CATEGORIES.filter(c=>c.type==='gasto').map(c=>`<option value="${c.id}" ${b&&b.category_id===c.id?'selected':''}>${c.icon||''} ${esc(c.name)}</option>`).join('');
  showModal(`<h3>${isEdit?'Editar':'Nuevo'} presupuesto</h3>
    <div class="field"><label>Categoría</label><select id="bg-cat" ${isEdit?'disabled':''}>${catOpts}</select></div>
    <div class="field"><label>Límite mensual (ARS)</label><input type="number" id="bg-amount" step="1000" value="${b?b.amount:''}"></div>`,
    async () => {
      const body = { category_id: parseInt(document.getElementById('bg-cat').value), amount: parseFloat(document.getElementById('bg-amount').value) };
      if (!body.amount || !body.category_id) { toast('Faltan datos','error'); return false; }
      await api('/api/budgets',{method:'POST',body}); toast(isEdit?'Actualizado':'Creado','success');
      loadBudgets();
    });
}
async function delBudget(id) { await api(`/api/budgets/${id}`,{method:'DELETE'}); toast('Borrado','success'); loadBudgets(); }

function loadTab(id) {
  ({overview:loadOverview, transacciones:loadTx, presupuestos:loadBudgets, recurrentes:loadRec, cuentas:loadAccTable, categorias:loadCatTable, cotizacion:loadCot, eventos:loadEv, tareas:loadTar, habitos:loadHabitos, recordatorios:loadRecs, notas:loadNotas}[id] || (()=>{}))();
}

loadOverview();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index(): return HTML
