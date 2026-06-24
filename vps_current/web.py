"""
Dashboard web multi-usuario.
- Login con usuario/contraseña por persona (las passwords se settean con /password en el bot).
- Cada usuario ve solo SUS datos por default.
- Toggle "mías / de ella / ambos" en la barra superior.
- El HTML del dashboard se carga desde dashboard.html (separar mantiene este archivo manejable).
"""

import os
import csv
import json
import sqlite3
import secrets
import hashlib
import urllib.request
import time as _time
import io
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body, Request, Response, Cookie, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse
from crud_v2 import router as crud_v2_router, init_crud_v2
# # >>> vencimientos patch
import vencimientos
import networth
import trends

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
TIMEZONE = os.environ.get("TIMEZONE", "America/Argentina/Buenos_Aires")
TZ = ZoneInfo(TIMEZONE)
DB_PATH = BASE_DIR / "data.db"
DASHBOARD_HTML_PATH = BASE_DIR / "dashboard.html"
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]

_rate_cache = {}
RATE_TTL = 900

# # >>> shared web patch
app = FastAPI(title="Asistente Dashboard")
init_crud_v2()
app.include_router(crud_v2_router)


# ─── DB ───────────────────────────────────────────────────────────────────
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try: yield conn
    finally: conn.close()


def now_local(): return datetime.now(TZ)


# ─── Auth ─────────────────────────────────────────────────────────────────
SESSIONS = {}  # token -> {"user_id": int, "expires": datetime}
SESSION_TTL = timedelta(days=30)


def verify_password(password, stored):
    if not stored or "$" not in stored: return False
    salt, h = stored.split("$", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def _purge_sessions():
    now = datetime.now()
    expired = [k for k, v in SESSIONS.items() if v["expires"] < now]
    for k in expired: SESSIONS.pop(k, None)


def _user_for_session(token):
    if not token: return None
    _purge_sessions()
    s = SESSIONS.get(token)
    if not s: return None
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=? AND active=1", (s["user_id"],)).fetchone()
    return dict(row) if row else None


def require_user(session: str = Cookie(None)):
    """Dependencia FastAPI: requiere sesión válida o tira 401."""
    u = _user_for_session(session)
    if not u: raise HTTPException(401, "Login requerido")
    return u


def get_user_by_name(name):
    if not name: return None
    with db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM users WHERE active=1").fetchall()]
    n = name.lower().strip()
    for r in rows:
        if r["name"].lower() == n or r["username"].lower() == n: return r
    for r in rows:
        if n in r["name"].lower() or n in r["username"].lower(): return r
    return None


def resolve_scope_uid(scope_cookie, user):
    """Devuelve user_id a usar para filtrar, o None si es 'compartido'."""
    s = (scope_cookie or "mine").strip().lower()
    if s in ("ours","shared","ambos","compartido","both"): return None
    if s.startswith("user:"):
        u = get_user_by_name(s.split(":",1)[1])
        if u: return u["id"]
    return user["id"]


def user_filter(scope_cookie, user, alias="t"):
    """Returns ("AND alias.user_id = ?", [uid]) tuple or ("", [])."""
    uid = resolve_scope_uid(scope_cookie, user)
    if uid is None: return "", []
    return f"AND {alias}.user_id = ?", [uid]


def user_filter_eq(scope_cookie, user, col="user_id"):
    """For simple WHERE col=? cases."""
    uid = resolve_scope_uid(scope_cookie, user)
    if uid is None: return "", []
    return f"AND {col} = ?", [uid]


# ─── Login / Logout ───────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>Login · Asistente</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,-apple-system,sans-serif}
body{background:linear-gradient(135deg,#0f172a,#1e293b);min-height:100vh;display:grid;place-items:center;color:#e2e8f0}
.box{background:#1e293b;padding:32px;border-radius:14px;width:340px;box-shadow:0 20px 60px rgba(0,0,0,.5);border:1px solid #334155}
h1{font-size:20px;margin-bottom:6px}.muted{color:#94a3b8;font-size:13px;margin-bottom:22px}
label{display:block;font-size:12px;color:#94a3b8;margin:14px 0 6px}
input{width:100%;padding:10px 12px;border-radius:8px;border:1px solid #334155;background:#0f172a;color:#e2e8f0;font-size:14px}
input:focus{outline:none;border-color:#3b82f6}
button{width:100%;margin-top:20px;padding:11px;border-radius:8px;border:0;background:#3b82f6;color:#fff;font-weight:600;cursor:pointer;font-size:14px}
button:hover{background:#2563eb}
.err{color:#f87171;font-size:12px;margin-top:12px;min-height:16px}
.hint{color:#64748b;font-size:11px;margin-top:18px;text-align:center}
</style></head><body>
<form class="box" onsubmit="return doLogin(event)">
  <h1>Asistente</h1>
  <div class="muted">Iniciá sesión</div>
  <label>Usuario</label><input id="u" autocomplete="username" autofocus>
  <label>Contraseña</label><input id="p" type="password" autocomplete="current-password">
  <button type="submit">Entrar</button>
  <div class="err" id="err"></div>
  <div class="hint">Cambiá tu password con /password en Telegram</div>
</form>
<script>
async function doLogin(ev){
  ev.preventDefault();
  const u=document.getElementById('u').value.trim(), p=document.getElementById('p').value;
  const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
  const j=await r.json().catch(()=>({}));
  if(r.ok){ location.href = j.next || '/'; }
  else{ document.getElementById('err').textContent = j.detail || 'Credenciales inválidas'; }
  return false;
}
</script></body></html>"""


@app.get("/login", response_class=HTMLResponse)
def login_page(session: str = Cookie(None)):
    if _user_for_session(session): return RedirectResponse("/", status_code=303)
    return HTMLResponse(LOGIN_HTML)


@app.post("/login")
def login(body: dict = Body(...), response: Response = None):
    username = (body.get("username") or "").strip().lower()
    password = body.get("password") or ""
    if not username or not password:
        raise HTTPException(400, "Faltan datos")
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE LOWER(username)=? AND active=1", (username,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"user_id": row["id"], "expires": datetime.now() + SESSION_TTL}
    resp = JSONResponse({"ok": True, "name": row["name"]})
    resp.set_cookie("session", token, max_age=int(SESSION_TTL.total_seconds()),
                    httponly=True, samesite="lax", secure=True)
    resp.set_cookie("scope", "mine", max_age=int(SESSION_TTL.total_seconds()), samesite="lax", secure=True)
    return resp


@app.get("/logout")
def logout(session: str = Cookie(None)):
    if session: SESSIONS.pop(session, None)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session"); resp.delete_cookie("scope")
    return resp


@app.get("/api/me")
def api_me(user=Depends(require_user), scope: str = Cookie("mine")):
    with db() as conn:
        all_users = [dict(r) for r in conn.execute("SELECT id,name,username,color FROM users WHERE active=1 ORDER BY id").fetchall()]
    other = [u for u in all_users if u["id"] != user["id"]]
    return {
        "id": user["id"], "name": user["name"], "username": user["username"], "color": user.get("color"),
        "scope": scope or "mine",
        "others": [{"name": u["name"], "scope_value": f"user:{u['name']}"} for u in other],
    }


@app.post("/api/set_scope")
def set_scope(body: dict = Body(...), user=Depends(require_user)):
    value = (body.get("value") or "mine").strip()
    resp = JSONResponse({"ok": True, "scope": value})
    resp.set_cookie("scope", value, max_age=int(SESSION_TTL.total_seconds()), samesite="lax", secure=True)
    return resp


# ─── Utils ────────────────────────────────────────────────────────────────
def get_dolar_rate(rate_type="blue"):
    now = _time.time()
    if rate_type in _rate_cache:
        ts, value = _rate_cache[rate_type]
        if now - ts < RATE_TTL: return value
    try:
        req = urllib.request.Request(f"https://dolarapi.com/v1/dolares/{rate_type}",
                                     headers={"User-Agent": "Mozilla/5.0 (asistente-web)"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        rate = (data.get("compra",0) + data.get("venta",0)) / 2
        if not rate: return None
        _rate_cache[rate_type] = (now, rate)
        return rate
    except Exception: return None


# ─── Overview ─────────────────────────────────────────────────────────────
@app.get("/api/overview")
def api_overview(user=Depends(require_user), scope: str = Cookie("mine")):
    now = now_local()
    mes_ini = now.strftime("%Y-%m-01")
    nowstr = now.strftime("%Y-%m-%dT%H:%M")
    uf_t, uf_p = user_filter(scope, user, "t")
    uf_x, uf_xp = user_filter_eq(scope, user, "user_id")
    scope_uid = resolve_scope_uid(scope, user)
    acc_filter = "" if scope_uid is None else "AND user_id=?"
    acc_params = [] if scope_uid is None else [scope_uid]

    with db() as conn:
        accounts = [dict(r) for r in conn.execute(
            f"SELECT * FROM accounts WHERE active=1 {acc_filter} ORDER BY name", acc_params).fetchall()]
        bals = conn.execute(
            f"SELECT account_id, currency, SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS bal "
            f"FROM transactions t WHERE 1=1 {uf_t} GROUP BY account_id, currency", uf_p).fetchall()
        m = {}
        for r in bals: m.setdefault(r['account_id'], []).append({"currency": r['currency'], "balance": r['bal']})
        for a in accounts: a['balances'] = m.get(a['id'], [])

        for a in accounts:
            if a['type'] == 'credito':
                pendientes = conn.execute(
                    f"SELECT id, amount, currency, description, total_installments, installments_fired "
                    f"FROM recurring WHERE active=1 AND account_id=? {acc_filter}",
                    [a['id']] + acc_params).fetchall()
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
            f"SELECT type, currency, SUM(amount) AS total FROM transactions t WHERE t.occurred_at>=? {uf_t} "
            f"GROUP BY type, currency", [mes_ini] + uf_p).fetchall()]
        por_cat = [dict(r) for r in conn.execute(
            f"SELECT COALESCE(c.name,'(sin categoría)') AS cat, c.color AS color, c.icon AS icon, t.currency, SUM(t.amount) AS total "
            f"FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            f"WHERE t.occurred_at>=? AND t.type='gasto' {uf_t} GROUP BY cat, t.currency ORDER BY total DESC",
            [mes_ini] + uf_p).fetchall()]
        por_acc = [dict(r) for r in conn.execute(
            f"SELECT a.name AS acc, a.color AS color, a.icon AS icon, t.currency, SUM(t.amount) AS total FROM transactions t "
            f"JOIN accounts a ON a.id=t.account_id WHERE t.occurred_at>=? AND t.type='gasto' {uf_t} "
            f"GROUP BY a.name, t.currency ORDER BY total DESC", [mes_ini] + uf_p).fetchall()]
        counts = {
            "eventos_proximos": conn.execute(f"SELECT COUNT(*) FROM eventos WHERE starts_at>=? {uf_x}", [nowstr] + uf_xp).fetchone()[0],
            "tareas_pendientes": conn.execute(f"SELECT COUNT(*) FROM tareas WHERE status='pendiente' {uf_x}", uf_xp).fetchone()[0],
            "recordatorios": conn.execute(f"SELECT COUNT(*) FROM recordatorios WHERE fired=0 AND remind_at>=? {uf_x}", [nowstr] + uf_xp).fetchone()[0],
            "recurrentes": conn.execute(f"SELECT COUNT(*) FROM recurring WHERE active=1 {uf_x}", uf_xp).fetchone()[0],
            "notas": conn.execute(f"SELECT COUNT(*) FROM notas WHERE 1=1 {uf_x}", uf_xp).fetchone()[0],
        }
    return {"accounts": accounts, "totales_mes": tot_mes, "por_categoria": por_cat,
            "por_cuenta": por_acc, "counts": counts, "mes_nombre": MESES[now.month-1], "year": now.year,
            "current_user": {"name": user["name"], "id": user["id"]}}


@app.get("/api/overview2")
def api_overview2(user=Depends(require_user), scope: str = Cookie("mine")):
    now = now_local()
    mes_ini = now.strftime("%Y-%m-01")
    hoy = now.strftime("%Y-%m-%d")
    blue = get_dolar_rate("blue") or 0
    uf_t, uf_p = user_filter(scope, user, "t")
    uf_x, uf_xp = user_filter_eq(scope, user, "user_id")
    scope_uid = resolve_scope_uid(scope, user)
    acc_filter = "" if scope_uid is None else "AND user_id=?"
    acc_params = [] if scope_uid is None else [scope_uid]

    def ars(amount, currency):
        return amount * (blue if currency in ("USD","EUR") and blue else 1)

    prev_last = now.replace(day=1) - timedelta(days=1)
    prev_ini = prev_last.strftime("%Y-%m-01")
    prev_alt = prev_last.replace(day=min(now.day, prev_last.day)).strftime("%Y-%m-%dT%H:%M")

    with db() as conn:
        accounts = [dict(r) for r in conn.execute(
            f"SELECT * FROM accounts WHERE active=1 {acc_filter} ORDER BY name", acc_params).fetchall()]
        bals = conn.execute(
            f"SELECT account_id, currency, SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS bal "
            f"FROM transactions t WHERE 1=1 {uf_t} GROUP BY account_id, currency", uf_p).fetchall()
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
        for r in conn.execute(
            f"SELECT amount,currency,total_installments,installments_fired FROM recurring "
            f"WHERE active=1 AND total_installments IS NOT NULL {uf_x}", uf_xp).fetchall():
            rem = r["total_installments"] - (r["installments_fired"] or 0)
            if rem > 0:
                cuotas_futuras += ars(r["amount"], r["currency"]) * rem; cuotas_n += rem

        def suma(tipo, desde, hasta=None):
            q = (f"SELECT t.currency, SUM(t.amount) AS s FROM transactions t "
                 f"LEFT JOIN categories c ON c.id=t.category_id "
                 f"WHERE t.type=? AND COALESCE(c.name,'')!='Transferencia' AND t.occurred_at>=? {uf_t}")
            params = [tipo, desde] + uf_p
            if hasta: q += " AND t.occurred_at<=?"; params.append(hasta)
            q += " GROUP BY t.currency"
            return sum(ars(r["s"], r["currency"]) for r in conn.execute(q, params).fetchall())

        gasto_mes = suma("gasto", mes_ini)
        gasto_prev_alt = suma("gasto", prev_ini, prev_alt)
        ingreso_mes = suma("ingreso", mes_ini)

        first = (now.replace(day=1) - timedelta(days=155)).strftime("%Y-%m-01")
        cf = {}
        for r in conn.execute(
            f"SELECT substr(t.occurred_at,1,7) AS ym, t.type, t.currency, SUM(t.amount) AS s "
            f"FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            f"WHERE t.occurred_at>=? AND COALESCE(c.name,'')!='Transferencia' {uf_t} "
            f"GROUP BY ym, t.type, t.currency", [first] + uf_p).fetchall():
            d = cf.setdefault(r["ym"], {"ingresos": 0, "gastos": 0})
            d["ingresos" if r["type"] == "ingreso" else "gastos"] += ars(r["s"], r["currency"])
        cashflow = [{"ym": k, **v} for k, v in sorted(cf.items())][-6:]

        hoy_items = []
        for r in conn.execute(
            f"SELECT id,title,starts_at,location FROM eventos WHERE substr(starts_at,1,10)=? {uf_x} ORDER BY starts_at",
            [hoy] + uf_xp).fetchall():
            hoy_items.append({"tipo": "evento", "titulo": r["title"], "sub": r["location"] or "", "hora": r["starts_at"][11:16]})
        for r in conn.execute(
            f"SELECT id,text,remind_at FROM recordatorios WHERE fired=0 AND substr(REPLACE(remind_at,' ','T'),1,10)=? {uf_x} ORDER BY remind_at",
            [hoy] + uf_xp).fetchall():
            hoy_items.append({"tipo": "recordatorio", "titulo": r["text"], "sub": "Recordatorio", "hora": r["remind_at"].replace(' ','T')[11:16]})
        for r in conn.execute(
            f"SELECT id,text,priority FROM tareas WHERE status='pendiente' AND substr(COALESCE(due_at,''),1,10)<=? AND due_at IS NOT NULL {uf_x} ORDER BY priority",
            [hoy] + uf_xp).fetchall():
            hoy_items.append({"tipo": "tarea", "titulo": r["text"], "sub": f"Tarea · prioridad {r['priority']}", "hora": "hoy"})
        for r in conn.execute(
            f"SELECT id,description,amount,currency FROM recurring WHERE active=1 AND next_occurrence<=? {uf_x} ORDER BY next_occurrence LIMIT 5",
            [hoy] + uf_xp).fetchall():
            hoy_items.append({"tipo": "recurrente", "titulo": f"{r['description']} ${r['amount']:,.0f}", "sub": "Recurrente · se cobra hoy", "hora": "auto"})

        por_cat = [dict(r) for r in conn.execute(
            f"SELECT COALESCE(c.name,'(sin categoría)') AS cat, c.color AS color, SUM(t.amount) AS total "
            f"FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            f"WHERE t.occurred_at>=? AND t.type='gasto' AND t.currency='ARS' AND COALESCE(c.name,'')!='Transferencia' {uf_t} "
            f"GROUP BY cat ORDER BY total DESC LIMIT 8", [mes_ini] + uf_p).fetchall()]

    return {
        "patrimonio_ars": patrimonio, "patrimonio_usd": (patrimonio / blue) if blue else None, "blue": blue,
        "kpis": {"gasto_mes": gasto_mes, "gasto_prev_alt": gasto_prev_alt, "ingreso_mes": ingreso_mes,
                 "deuda_tarjetas": deuda, "cuotas_futuras": cuotas_futuras, "cuotas_n": cuotas_n,
                 "disponible": disponible},
        "cashflow": cashflow, "hoy": hoy_items, "por_categoria": por_cat,
        "mes_nombre": MESES[now.month-1], "year": now.year, "dia": now.day,
    }


# ─── Accounts ─────────────────────────────────────────────────────────────
@app.get("/api/accounts")
def api_accounts(include_inactive: bool = False, user=Depends(require_user), scope: str = Cookie("mine")):
    scope_uid = resolve_scope_uid(scope, user)
    with db() as conn:
        base = "SELECT * FROM accounts"
        params = []
        conds = []
        if not include_inactive: conds.append("active=1")
        if scope_uid is not None:
            conds.append("user_id=?"); params.append(scope_uid)
        if conds: base += " WHERE " + " AND ".join(conds)
        base += " ORDER BY active DESC, name" if include_inactive else " ORDER BY name"
        rows = conn.execute(base, params).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/accounts")
def api_acc_create(body: dict = Body(...), user=Depends(require_user)):
    name = (body.get("name") or "").strip()
    if not name: raise HTTPException(400, "Nombre requerido")
    with db() as conn:
        exists = conn.execute("SELECT id FROM accounts WHERE name=? AND user_id=?", (name, user["id"])).fetchone()
        if exists: raise HTTPException(400, "Ya tenés una cuenta con ese nombre")
        cur = conn.execute("INSERT INTO accounts (name,type,color,icon,active,closing_day,due_day,user_id) VALUES (?,?,?,?,1,?,?,?)",
            (name, body.get("type","efectivo"), body.get("color","#60a5fa"), body.get("icon","💳"), body.get("closing_day"), body.get("due_day"), user["id"]))
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


@app.patch("/api/accounts/{aid}")
def api_acc_update(aid: int, body: dict = Body(...), user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM accounts WHERE id=?", (aid,)).fetchone()
        if not row: raise HTTPException(404, "No existe")
        if row["user_id"] != user["id"]: raise HTTPException(403, "No es tu cuenta")
        fields=[]; params=[]
        for k in ("name","type","color","icon","closing_day","due_day"):
            if k in body: fields.append(f"{k}=?"); params.append(body[k])
        if "active" in body: fields.append("active=?"); params.append(1 if body["active"] else 0)
        if not fields: raise HTTPException(400, "Sin cambios")
        params.append(aid)
        conn.execute(f"UPDATE accounts SET {', '.join(fields)} WHERE id=?", params); conn.commit()
    return {"ok": True}


@app.delete("/api/accounts/{aid}")
def api_acc_delete(aid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM accounts WHERE id=?", (aid,)).fetchone()
        if not row: raise HTTPException(404, "No existe")
        if row["user_id"] != user["id"]: raise HTTPException(403, "No es tu cuenta")
        in_use = conn.execute("SELECT COUNT(*) FROM transactions WHERE account_id=?", (aid,)).fetchone()[0]
        if in_use:
            conn.execute("UPDATE accounts SET active=0 WHERE id=?", (aid,)); conn.commit()
            return {"ok": True, "archived": True}
        conn.execute("DELETE FROM accounts WHERE id=?", (aid,)); conn.commit()
    return {"ok": True}


# ─── Categories (compartidas) ─────────────────────────────────────────────
@app.get("/api/categories")
def api_categories(include_inactive: bool = False, user=Depends(require_user)):
    with db() as conn:
        if include_inactive:
            rows = conn.execute("SELECT * FROM categories ORDER BY active DESC, type, name").fetchall()
        else:
            rows = conn.execute("SELECT * FROM categories WHERE active=1 ORDER BY type, name").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/categories")
def api_cat_create(body: dict = Body(...), user=Depends(require_user)):
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
def api_cat_update(cid: int, body: dict = Body(...), user=Depends(require_user)):
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
def api_cat_delete(cid: int, user=Depends(require_user)):
    with db() as conn:
        in_use = conn.execute("SELECT COUNT(*) FROM transactions WHERE category_id=?", (cid,)).fetchone()[0]
        if in_use:
            conn.execute("UPDATE categories SET active=0 WHERE id=?", (cid,)); conn.commit()
            return {"ok": True, "archived": True}
        conn.execute("DELETE FROM categories WHERE id=?", (cid,)); conn.commit()
    return {"ok": True}


# ─── Transactions ─────────────────────────────────────────────────────────
@app.get("/api/transactions")
def api_transactions(year: int = None, month: int = None, account_id: int = None,
                      category_id: int = None, currency: str = None, type: str = None,
                      q: str = None, limit: int = 200, offset: int = 0,
                      user=Depends(require_user), scope: str = Cookie("mine")):
    uf_t, uf_p = user_filter(scope, user, "t")
    where = ["1=1"]; params = []
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
    wc = " AND ".join(where) + " " + uf_t
    final_params = params + uf_p
    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM transactions t WHERE {wc}", final_params).fetchone()[0]
        rows = conn.execute(
            f"SELECT t.*, a.name AS acc_name, a.color AS acc_color, a.icon AS acc_icon, "
            f"c.name AS cat_name, c.color AS cat_color, c.icon AS cat_icon, "
            f"r.description AS rec_desc, r.total_installments AS rec_total, r.installments_fired AS rec_fired, "
            f"u.name AS owner_name "
            f"FROM transactions t JOIN accounts a ON a.id=t.account_id "
            f"LEFT JOIN categories c ON c.id=t.category_id "
            f"LEFT JOIN recurring r ON r.id=t.recurring_id "
            f"LEFT JOIN users u ON u.id=t.user_id "
            f"WHERE {wc} ORDER BY t.occurred_at DESC, t.id DESC LIMIT ? OFFSET ?",
            final_params + [limit, offset]).fetchall()
        sums = conn.execute(f"SELECT t.type, t.currency, SUM(t.amount) AS total FROM transactions t WHERE {wc} GROUP BY t.type, t.currency", final_params).fetchall()
    return {"items": [dict(r) for r in rows], "total": total, "sums": [dict(r) for r in sums]}


@app.post("/api/transactions")
def api_tx_create(body: dict = Body(...), user=Depends(require_user)):
    required = ("amount", "account_id", "occurred_at", "type")
    for k in required:
        if k not in body or body[k] is None: raise HTTPException(400, f"Falta {k}")
    with db() as conn:
        # validar que la cuenta sea del usuario
        acc = conn.execute("SELECT user_id FROM accounts WHERE id=?", (int(body["account_id"]),)).fetchone()
        if not acc: raise HTTPException(400, "Cuenta inexistente")
        if acc["user_id"] != user["id"]: raise HTTPException(403, "Esa cuenta no es tuya")
        cur = conn.execute(
            "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,user_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (body["type"], float(body["amount"]), body.get("currency","ARS"),
             int(body["account_id"]), int(body["category_id"]) if body.get("category_id") else None,
             body.get("description"), body["occurred_at"], user["id"]))
        conn.commit()
    return {"id": cur.lastrowid, "ok": True}


@app.patch("/api/transactions/{tid}")
def api_patch_tx(tid: int, body: dict = Body(...), user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM transactions WHERE id=?", (tid,)).fetchone()
        if not row: raise HTTPException(404, "No existe")
        if row["user_id"] != user["id"]: raise HTTPException(403, "No es tuya")
        fields=[]; params=[]
        for k in ("amount","currency","description","occurred_at","type"):
            if k in body: fields.append(f"{k}=?"); params.append(body[k])
        if "account_id" in body:
            acc = conn.execute("SELECT user_id FROM accounts WHERE id=?", (int(body["account_id"]),)).fetchone()
            if not acc or acc["user_id"] != user["id"]: raise HTTPException(403, "Cuenta destino no es tuya")
            fields.append("account_id=?"); params.append(int(body["account_id"]))
        if "category_id" in body:
            v = body["category_id"]; fields.append("category_id=?")
            params.append(int(v) if v else None)
        if not fields: raise HTTPException(400, "Sin cambios")
        params.append(tid)
        conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id=?", params); conn.commit()
    return {"ok": True}


@app.delete("/api/transactions/{tid}")
def del_tx(tid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM transactions WHERE id=?", (tid,)).fetchone()
        if not row: raise HTTPException(404, "No existe")
        if row["user_id"] != user["id"]: raise HTTPException(403, "No es tuya")
        conn.execute("DELETE FROM transactions WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.post("/api/transactions/bulk_delete")
def bulk_delete_tx(body: dict = Body(...), user=Depends(require_user)):
    ids = body.get("ids") or []
    if not ids: raise HTTPException(400, "Sin ids")
    placeholders = ",".join("?" * len(ids))
    with db() as conn:
        owned = conn.execute(
            f"SELECT COUNT(*) FROM transactions WHERE id IN ({placeholders}) AND user_id=?",
            ids + [user["id"]]).fetchone()[0]
        if owned != len(ids): raise HTTPException(403, "Alguna no es tuya")
        conn.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", ids); conn.commit()
    return {"ok": True, "count": len(ids)}


@app.post("/api/transactions/bulk_move")
def bulk_move_tx(body: dict = Body(...), user=Depends(require_user)):
    ids = body.get("ids") or []
    if not ids: raise HTTPException(400, "Sin ids")
    sets = []; params = []
    if body.get("account_id"):
        with db() as conn:
            acc = conn.execute("SELECT user_id FROM accounts WHERE id=?", (int(body["account_id"]),)).fetchone()
        if not acc or acc["user_id"] != user["id"]: raise HTTPException(403, "Cuenta destino no es tuya")
        sets.append("account_id=?"); params.append(int(body["account_id"]))
    if body.get("category_id"): sets.append("category_id=?"); params.append(int(body["category_id"]))
    if not sets: raise HTTPException(400, "Sin cambios")
    placeholders = ",".join("?" * len(ids))
    with db() as conn:
        owned = conn.execute(
            f"SELECT COUNT(*) FROM transactions WHERE id IN ({placeholders}) AND user_id=?",
            ids + [user["id"]]).fetchone()[0]
        if owned != len(ids): raise HTTPException(403, "Alguna no es tuya")
        conn.execute(f"UPDATE transactions SET {', '.join(sets)} WHERE id IN ({placeholders})", params + ids)
        conn.commit()
    return {"ok": True, "count": len(ids)}


@app.get("/api/export.csv")
def export_csv(year: int = None, month: int = None, user=Depends(require_user), scope: str = Cookie("mine")):
    uf_t, uf_p = user_filter(scope, user, "t")
    where = ["1=1"]; params = []
    if year and month:
        start = f"{year}-{month:02d}-01"
        em, ey = (month+1, year) if month < 12 else (1, year+1)
        end = f"{ey}-{em:02d}-01"
        where.append("t.occurred_at >= ? AND t.occurred_at < ?"); params.extend([start, end])
    wc = " AND ".join(where) + " " + uf_t
    final_params = params + uf_p
    with db() as conn:
        rows = conn.execute(
            f"SELECT t.id, t.occurred_at, t.type, t.amount, t.currency, a.name AS account, "
            f"c.name AS category, t.description, u.name AS owner FROM transactions t JOIN accounts a ON a.id=t.account_id "
            f"LEFT JOIN categories c ON c.id=t.category_id LEFT JOIN users u ON u.id=t.user_id "
            f"WHERE {wc} ORDER BY t.occurred_at DESC", final_params).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id","fecha","tipo","monto","moneda","cuenta","categoria","descripcion","persona"])
    for r in rows:
        w.writerow([r['id'], r['occurred_at'], r['type'], r['amount'], r['currency'],
                    r['account'], r['category'] or '', r['description'] or '', r['owner'] or ''])
    buf.seek(0)
    fn = f"transacciones_{year}_{month:02d}.csv" if year and month else "transacciones.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fn}"})


# ─── Recurring ────────────────────────────────────────────────────────────
@app.get("/api/recurring")
def api_recurring(include_inactive: bool = False, user=Depends(require_user), scope: str = Cookie("mine")):
    uf_x, uf_xp = user_filter_eq(scope, user, "r.user_id")
    with db() as conn:
        sql = ("SELECT r.*, a.name AS acc_name, a.color AS acc_color, a.icon AS acc_icon, "
               "c.name AS cat_name, c.color AS cat_color, c.icon AS cat_icon "
               "FROM recurring r JOIN accounts a ON a.id=r.account_id "
               "LEFT JOIN categories c ON c.id=r.category_id WHERE 1=1 ")
        params = []
        if not include_inactive: sql += "AND r.active=1 "
        sql += uf_x + " ORDER BY r.active DESC, r.next_occurrence"
        rows = conn.execute(sql, uf_xp).fetchall()
    return [dict(r) for r in rows]


@app.patch("/api/recurring/{rid}")
def api_patch_rec(rid: int, body: dict = Body(...), user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM recurring WHERE id=?", (rid,)).fetchone()
        if not row: raise HTTPException(404, "No existe")
        if row["user_id"] != user["id"]: raise HTTPException(403, "No es tuya")
        fields=[]; params=[]
        for k in ("amount","description","day_of_month","next_occurrence","total_installments","installments_fired"):
            if k in body: fields.append(f"{k}=?"); params.append(body[k])
        if "active" in body: fields.append("active=?"); params.append(1 if body["active"] else 0)
        if not fields: raise HTTPException(400, "Sin cambios")
        params.append(rid)
        conn.execute(f"UPDATE recurring SET {', '.join(fields)} WHERE id=?", params); conn.commit()
    return {"ok": True}


@app.delete("/api/recurring/{rid}")
def del_rec_rec(rid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM recurring WHERE id=?", (rid,)).fetchone()
        if not row: raise HTTPException(404, "No existe")
        if row["user_id"] != user["id"]: raise HTTPException(403, "No es tuya")
        conn.execute("DELETE FROM recurring WHERE id=?", (rid,)); conn.commit()
    return {"ok": True}


# ─── Eventos / Tareas / Habitos / Recordatorios / Notas ───────────────────
@app.get("/api/eventos")
def api_eventos(past: bool = False, user=Depends(require_user), scope: str = Cookie("mine")):
    uf_x, uf_xp = user_filter_eq(scope, user, "user_id")
    nowstr = now_local().strftime("%Y-%m-%dT%H:%M")
    with db() as conn:
        if past:
            rows = conn.execute(f"SELECT * FROM eventos WHERE starts_at<? {uf_x} ORDER BY starts_at DESC LIMIT 50",
                                [nowstr] + uf_xp).fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM eventos WHERE starts_at>=? {uf_x} ORDER BY starts_at ASC",
                                [nowstr] + uf_xp).fetchall()
        events = [dict(r) for r in rows]
        # adjuntar recordatorios linkeados a cada evento
        if events:
            ids = [e["id"] for e in events]
            ph = ",".join("?" * len(ids))
            recs = conn.execute(
                f"SELECT * FROM recordatorios WHERE event_id IN ({ph}) ORDER BY remind_at ASC", ids).fetchall()
            by_ev = {}
            for r in recs:
                by_ev.setdefault(r["event_id"], []).append(dict(r))
            for e in events:
                e["reminders"] = by_ev.get(e["id"], [])
    return events


@app.delete("/api/eventos/{eid}")
def del_ev(eid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM eventos WHERE id=?", (eid,)).fetchone()
        if row and row["user_id"] != user["id"]: raise HTTPException(403, "No es tuyo")
        conn.execute("DELETE FROM eventos WHERE id=?", (eid,)); conn.commit()
    return {"ok": True}


@app.get("/api/tareas")
def api_tareas(status: str = "pendiente", user=Depends(require_user), scope: str = Cookie("mine")):
    # incluye items compartidos (shared=1) ademas de los propios
    scope_uid = resolve_scope_uid(scope, user)
    if scope_uid is not None:
        wuser = "(user_id=? OR COALESCE(shared,0)=1)"
        params_user = [scope_uid]
    else:
        wuser = "1=1"; params_user = []
    with db() as conn:
        if status == "all":
            rows = conn.execute(
                f"SELECT * FROM tareas WHERE {wuser} ORDER BY created_at DESC LIMIT 200",
                params_user).fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM tareas WHERE status=? AND {wuser} ORDER BY "
                f"CASE priority WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, "
                f"COALESCE(due_at,'9999'), id", [status] + params_user).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/tareas")
def crear_tarea(body: dict = Body(...), user=Depends(require_user)):
    text = (body.get("text") or "").strip()
    if not text: raise HTTPException(400, "Texto requerido")
    with db() as conn:
        cur = conn.execute("INSERT INTO tareas (text,priority,due_at,user_id) VALUES (?,?,?,?)",
            (text, body.get("priority","media"), body.get("due_at"), user["id"]))
        conn.commit()
    return {"id": cur.lastrowid, "ok": True}


@app.post("/api/tareas/{tid}/done")
def t_done(tid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id, COALESCE(shared,0) AS sh FROM tareas WHERE id=?", (tid,)).fetchone()
        if row and row["user_id"] != user["id"] and not row["sh"]:
            raise HTTPException(403, "No es tuya")
        conn.execute("UPDATE tareas SET status='hecha', completed_at=datetime('now') WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.post("/api/tareas/{tid}/undone")
def t_undone(tid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id, COALESCE(shared,0) AS sh FROM tareas WHERE id=?", (tid,)).fetchone()
        if row and row["user_id"] != user["id"] and not row["sh"]:
            raise HTTPException(403, "No es tuya")
        conn.execute("UPDATE tareas SET status='pendiente', completed_at=NULL WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.delete("/api/tareas/{tid}")
def del_tar(tid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id, COALESCE(shared,0) AS sh FROM tareas WHERE id=?", (tid,)).fetchone()
        if row and row["user_id"] != user["id"] and not row["sh"]:
            raise HTTPException(403, "No es tuya")
        conn.execute("DELETE FROM tareas WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.get("/api/habitos")
def api_habitos(days: int = 30, user=Depends(require_user), scope: str = Cookie("mine")):
    uf_x, uf_xp = user_filter_eq(scope, user, "user_id")
    desde = (now_local() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with db() as conn:
        items = [dict(r) for r in conn.execute(
            f"SELECT * FROM habito_logs WHERE logged_at>=? {uf_x} ORDER BY logged_at DESC", [desde] + uf_xp).fetchall()]
        resumen = [dict(r) for r in conn.execute(
            f"SELECT name, COUNT(*) AS cnt, SUM(value) AS total, unit FROM habito_logs "
            f"WHERE logged_at>=? {uf_x} GROUP BY name, unit ORDER BY cnt DESC", [desde] + uf_xp).fetchall()]
    return {"items": items, "resumen": resumen, "days": days}


@app.get("/api/recordatorios")
def api_recs(include_fired: bool = False, user=Depends(require_user), scope: str = Cookie("mine")):
    uf_x, uf_xp = user_filter_eq(scope, user, "user_id")
    with db() as conn:
        if include_fired:
            rows = conn.execute(f"SELECT * FROM recordatorios WHERE 1=1 {uf_x} ORDER BY remind_at DESC LIMIT 100", uf_xp).fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM recordatorios WHERE fired=0 {uf_x} ORDER BY remind_at ASC", uf_xp).fetchall()
    return [dict(r) for r in rows]


@app.delete("/api/recordatorios/{rid}")
def del_rec(rid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM recordatorios WHERE id=?", (rid,)).fetchone()
        if row and row["user_id"] != user["id"]: raise HTTPException(403, "No es tuyo")
        conn.execute("DELETE FROM recordatorios WHERE id=?", (rid,)); conn.commit()
    return {"ok": True}


@app.get("/api/notas")
def api_notas(q: str = None, limit: int = 50, user=Depends(require_user), scope: str = Cookie("mine")):
    scope_uid = resolve_scope_uid(scope, user)
    if scope_uid is not None:
        wuser = "(user_id=? OR COALESCE(shared,0)=1)"
        params_user = [scope_uid]
    else:
        wuser = "1=1"; params_user = []
    with db() as conn:
        if q:
            rows = conn.execute(
                f"SELECT * FROM notas WHERE text LIKE ? AND {wuser} ORDER BY created_at DESC LIMIT ?",
                [f"%{q}%"] + params_user + [limit]).fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM notas WHERE {wuser} ORDER BY created_at DESC LIMIT ?",
                params_user + [limit]).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/notas")
def crear_nota(body: dict = Body(...), user=Depends(require_user)):
    text = (body.get("text") or "").strip()
    if not text: raise HTTPException(400, "Texto requerido")
    tags = json.dumps(body.get("tags") or [], ensure_ascii=False)
    with db() as conn:
        cur = conn.execute("INSERT INTO notas (text,tags,user_id) VALUES (?,?,?)", (text, tags, user["id"])); conn.commit()
    return {"id": cur.lastrowid, "ok": True}


@app.delete("/api/notas/{nid}")
def del_nota(nid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id, COALESCE(shared,0) AS sh FROM notas WHERE id=?", (nid,)).fetchone()
        if row and row["user_id"] != user["id"] and not row["sh"]:
            raise HTTPException(403, "No es tuya")
        conn.execute("DELETE FROM notas WHERE id=?", (nid,)); conn.commit()
    return {"ok": True}


@app.get("/api/cotizacion")
def api_cotizacion(user=Depends(require_user)):
    return {t: get_dolar_rate(t) for t in ["oficial","blue","mep","cripto"]}


@app.get("/api/currencies")
def api_currencies(user=Depends(require_user), scope: str = Cookie("mine")):
    """Monedas realmente presentes en los datos (transactions + recurring),
    respetando el scope. Sirve para poblar dinámicamente los filtros de moneda.
    Siempre incluye ARS como base. Orden: ARS, USD, EUR primero, resto alfabético."""
    uf_t, uf_p = user_filter(scope, user, "t")
    uf_x, uf_xp = user_filter_eq(scope, user, "user_id")
    found = set()
    with db() as conn:
        for r in conn.execute(
            f"SELECT DISTINCT currency FROM transactions t WHERE currency IS NOT NULL {uf_t}", uf_p).fetchall():
            if r["currency"]:
                found.add(r["currency"])
        for r in conn.execute(
            f"SELECT DISTINCT currency FROM recurring WHERE currency IS NOT NULL {uf_x}", uf_xp).fetchall():
            if r["currency"]:
                found.add(r["currency"])
    found.add("ARS")
    pref = ["ARS", "USD", "EUR"]
    ordered = [c for c in pref if c in found] + sorted(c for c in found if c not in pref)
    return {"currencies": ordered}


# ─── Patrimonio / Net Worth ────────────────────────────────────────────────
def _web_takenos_manual():
    with db() as conn:
        r = conn.execute(
            "SELECT value FROM user_settings WHERE key=? ORDER BY user_id LIMIT 1",
            (networth.fx.TAKENOS_RATE_KEY,)).fetchone()
    return float(r["value"]) if r and r["value"] else None


def _web_account_balances(scope_uid):
    rows = []
    with db() as conn:
        if scope_uid is None:
            accs = conn.execute(
                "SELECT id, name, icon, preferred_fx_rate FROM accounts WHERE active=1").fetchall()
        else:
            accs = conn.execute(
                "SELECT id, name, icon, preferred_fx_rate FROM accounts WHERE active=1 AND user_id=?",
                (scope_uid,)).fetchall()
        for a in accs:
            bals = conn.execute(
                "SELECT currency, SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS bal "
                "FROM transactions WHERE account_id=? GROUP BY currency", (a["id"],)).fetchall()
            for b in bals:
                if b["bal"] is None or b["bal"] == 0:
                    continue
                rows.append({
                    "account_id": a["id"], "name": a["name"], "icon": a["icon"] or "",
                    "currency": b["currency"], "balance": b["bal"],
                    "rate_type": networth.fx.resolve_rate_type(a["preferred_fx_rate"], default="blue"),
                })
    return rows


@app.get("/api/networth")
def api_networth(user=Depends(require_user), scope: str = Cookie("mine")):
    scope_uid = resolve_scope_uid(scope, user)
    # serie historica de snapshots
    with db() as conn:
        if scope_uid is None:
            # 'ambos': sumar los snapshots de ambos usuarios por dia
            rows = conn.execute(
                "SELECT substr(taken_at,1,10) AS day, SUM(total_ars) AS total_ars, SUM(total_usd) AS total_usd "
                "FROM net_worth_snapshots "
                "GROUP BY day ORDER BY day").fetchall()
        else:
            rows = conn.execute(
                "SELECT substr(taken_at,1,10) AS day, total_ars, total_usd "
                "FROM net_worth_snapshots WHERE user_id=? ORDER BY taken_at", (scope_uid,)).fetchall()
    series = [{"day": r["day"], "total_ars": r["total_ars"], "total_usd": r["total_usd"]} for r in rows]

    # punto "ahora" en vivo (no persiste; solo para el grafico/encabezado)
    now_point = None
    try:
        balances = _web_account_balances(scope_uid)
        res = networth.net_worth(balances, get_dolar_rate, takenos_manual=_web_takenos_manual())
        now_point = {
            "total_ars": res["total_ars"], "total_usd": res["total_usd"],
            "detail": sorted(res["detail"], key=lambda x: x["value_ars"], reverse=True),
        }
    except Exception:
        now_point = None
    return {"series": series, "now": now_point}


# ─── Tendencias (trend charts) ─────────────────────────────────────────────
@app.get("/api/trends")
def api_trends(months: int = 6, by: str = "total", currency: str = "ARS",
               user=Depends(require_user), scope: str = Cookie("mine")):
    months = max(1, min(12, months))
    now = now_local()
    # primer dia del mes (months-1) atras
    y, m = now.year, now.month
    sy = y + (m - 1 - (months - 1)) // 12
    sm = (m - 1 - (months - 1)) % 12 + 1
    first = f"{sy:04d}-{sm:02d}-01"
    uf_t, uf_p = user_filter(scope, user, "t")
    today = now.strftime("%Y-%m-%d")
    with db() as conn:
        if by == "category":
            rows = [dict(r) for r in conn.execute(
                f"SELECT substr(t.occurred_at,1,7) AS ym, "
                f"COALESCE(c.name,'(sin categoría)') AS cat, t.currency, SUM(t.amount) AS total "
                f"FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
                f"WHERE t.occurred_at>=? AND t.type='gasto' "
                f"AND COALESCE(c.name,'')!='Transferencia' {uf_t} "
                f"GROUP BY ym, cat, t.currency", [first] + uf_p).fetchall()]
            return trends.bucket_by_category(rows, months=months, today=today, currency=currency)
        rows = [dict(r) for r in conn.execute(
            f"SELECT substr(t.occurred_at,1,7) AS ym, t.type, t.currency, SUM(t.amount) AS total "
            f"FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            f"WHERE t.occurred_at>=? AND COALESCE(c.name,'')!='Transferencia' {uf_t} "
            f"GROUP BY ym, t.type, t.currency", [first] + uf_p).fetchall()]
        return trends.monthly_trend(rows, months=months, today=today)


# ─── Calendario: pagos (plata) + agenda (vida) ──────────────────────────────
# Conceptualmente hay tres orígenes distintos y NO deben mezclarse bajo "pagos":
#   • pagos  = recurrentes + vencimientos de tarjeta (tienen monto)
#   • agenda = eventos + recordatorios (vida: turnos, fútbol, etc., sin monto)
# Se devuelven listas separadas. `items` se mantiene (combinado) por
# compatibilidad con consumidores viejos, pero la UI usa pagos/agenda.
@app.get("/api/upcoming")
def api_upcoming(days: int = 45, user=Depends(require_user), scope: str = Cookie("mine")):
    days = max(7, min(120, days))
    now = now_local()
    horizon = (now + timedelta(days=days)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    nowstr = now.strftime("%Y-%m-%dT%H:%M")
    uf_x, uf_xp = user_filter_eq(scope, user, "user_id")
    scope_uid = resolve_scope_uid(scope, user)
    pagos = []
    agenda = []
    with db() as conn:
        # --- PAGOS: recurrentes ---
        for r in conn.execute(
            f"SELECT description, amount, currency, next_occurrence "
            f"FROM recurring WHERE active=1 AND next_occurrence<=? {uf_x} "
            f"ORDER BY next_occurrence", [horizon] + uf_xp).fetchall():
            pagos.append({"date": r["next_occurrence"][:10], "kind": "recurrente",
                          "title": r["description"], "amount": r["amount"], "currency": r["currency"]})
        # --- AGENDA: eventos (vida) ---
        for r in conn.execute(
            f"SELECT title, starts_at, location FROM eventos "
            f"WHERE starts_at>=? AND substr(starts_at,1,10)<=? {uf_x} ORDER BY starts_at",
            [nowstr, horizon] + uf_xp).fetchall():
            agenda.append({"date": r["starts_at"][:10], "datetime": r["starts_at"],
                           "kind": "evento", "title": r["title"],
                           "sub": r["location"] or "", "amount": None, "currency": None})
        # --- AGENDA: recordatorios (vida) ---
        for r in conn.execute(
            f"SELECT text, REPLACE(remind_at,' ','T') AS ra FROM recordatorios "
            f"WHERE fired=0 AND REPLACE(remind_at,' ','T')<=? {uf_x} ORDER BY ra",
            [horizon + "T23:59"] + uf_xp).fetchall():
            agenda.append({"date": r["ra"][:10], "datetime": r["ra"],
                           "kind": "recordatorio", "title": r["text"],
                           "sub": "", "amount": None, "currency": None})
        cards_sql = ("SELECT * FROM accounts WHERE type='credito' AND active=1"
                     + ("" if scope_uid is None else " AND user_id=?"))
        cards = conn.execute(cards_sql, () if scope_uid is None else (scope_uid,)).fetchall()
    from datetime import date as _date
    for c in cards:
        d = vencimientos.calcular_vencimiento(str(DB_PATH), dict(c), _date.today())
        if d.get("error") or d["next_due"][:10] > horizon:
            continue
        for r in d.get("ciclo_cerrado", []):
            pagos.append({"date": d["next_due"][:10], "kind": "tarjeta",
                          "title": f"Vence {c['name']}", "amount": r["total"], "currency": r["currency"]})
    pagos.sort(key=lambda x: x["date"])
    agenda.sort(key=lambda x: x.get("datetime") or x["date"])
    items = sorted(pagos + agenda, key=lambda x: x["date"])  # compat
    return {"today": today, "horizon": horizon,
            "pagos": pagos, "agenda": agenda, "items": items}


# ─── User bar inyectada en el dashboard ───────────────────────────────────

# >>> vencimientos widget
VENC_WIDGET = """<div id="venc-widget" style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;margin:0 0 18px;color:#e2e8f0;font:14px system-ui;font-family:system-ui,-apple-system,sans-serif">
  <div style="font-size:13px;font-weight:500;letter-spacing:.5px;text-transform:uppercase;margin-bottom:12px;color:#cbd5e1">💳 Próximos vencimientos</div>
  <div id="venc-cards" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px">cargando...</div>
</div>
<style>
  .vcard{background:#0f172a;border:1px solid #334155;border-radius:10px;padding:11px 14px;font-size:13px}
  .vcard .vt{font-weight:600;margin-bottom:6px;color:#e2e8f0}
  .vcard .va{color:#e2e8f0;margin-bottom:3px}
  .vcard .vo{color:#94a3b8;font-size:12px}
  .vcard.err{color:#f87171}
</style>
<script>
(async function(){
  try{
    const r = await fetch('/api/vencimientos');
    if(!r.ok){ document.getElementById('venc-cards').innerHTML='<span style=\"color:#94a3b8\">error cargando</span>'; return; }
    const data = await r.json();
    const wrap = document.getElementById('venc-cards');
    if(!data.length){
      wrap.innerHTML = '<div style=\"color:#94a3b8;font-size:13px\">Sin tarjetas con cierre/vencimiento setteado. Corre migrate_tarjetas.py.</div>';
      return;
    }
    const fmtDate = s => { if(!s) return ''; const p=s.split('-'); return p[2]+'/'+p[1]; };
    const fmtN = n => Number(n||0).toLocaleString('es-AR',{minimumFractionDigits:2,maximumFractionDigits:2});
    wrap.innerHTML = data.map(d => {
      if(d.error) return '<div class=\"vcard err\">'+(d.icon||'💳')+' '+d.account_name+'<br><span style=\"font-size:11px\">'+d.error+'</span></div>';
      const tot = (d.ciclo_cerrado||[]).map(c => '$'+fmtN(c.total)+' '+c.currency).join(' + ') || '$0,00';
      const open = (d.ciclo_abierto||[]).map(c => '$'+fmtN(c.total)+' '+c.currency).join(' + ') || '$0,00';
      return '<div class=\"vcard\">'
        +'<div class=\"vt\">'+(d.icon||'💳')+' '+d.account_name+'</div>'
        +'<div class=\"va\">A pagar el <b>'+fmtDate(d.next_due)+'</b>: <b>'+tot+'</b></div>'
        +'<div class=\"vo\">Mes en curso (cierra '+fmtDate(d.next_closing)+'): '+open+'</div>'
      +'</div>';
    }).join('');
  }catch(e){ console.error('vencimientos widget:', e); }
})();
</script>"""


USER_BAR = """<div id="cw-userbar" style="position:fixed;top:0;left:0;right:0;z-index:9999;background:#0b1220;color:#e2e8f0;padding:0 16px;height:38px;font:13px system-ui;display:flex;gap:10px;align-items:center;border-bottom:1px solid #1e293b">
  <span style="font-weight:600;display:flex;align-items:center;gap:5px"><span style="font-size:14px">👤</span> __NAME__</span>
  <span style="opacity:.55;font-size:11px;text-transform:uppercase;letter-spacing:.5px;margin-left:6px">Ver</span>
  <div class="cw-scope-group" style="display:flex;gap:2px;background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:2px">
  <button class="cw-scope-btn" data-scope="mine">Mías</button>
  __OTHER_BUTTONS__
  <button class="cw-scope-btn" data-scope="ours">Ambos</button>
  </div>
  <span style="flex:1"></span>
  <a href="/logout" style="color:#94a3b8;text-decoration:none;font-size:12px;padding:4px 8px;border-radius:6px">Salir →</a>
</div>
<style>
  body{padding-top:38px !important}
  #cw-userbar .cw-scope-btn{background:none;border:none;color:#94a3b8;padding:4px 11px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;line-height:1.1;transition:background .15s,color .15s}
  #cw-userbar .cw-scope-btn:hover{color:#e2e8f0}
  #cw-userbar .cw-scope-btn.active{background:#2563eb !important;color:#fff !important}
  #cw-userbar a[href="/logout"]:hover{background:#1e293b;color:#e2e8f0}
</style>
<script>
(function(){
  const cur = (document.cookie.match(/scope=([^;]+)/)||[])[1] || 'mine';
  document.querySelectorAll('.cw-scope-btn').forEach(b => {
    if (b.dataset.scope === cur) b.classList.add('active');
    b.onclick = async () => {
      await fetch('/api/set_scope',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:b.dataset.scope})});
      location.reload();
    };
  });
})();
</script>"""


def _build_user_bar(user):
    with db() as conn:
        others = [dict(r) for r in conn.execute(
            "SELECT name FROM users WHERE id!=? AND active=1", (user["id"],)).fetchall()]
    btns = ""
    for o in others:
        btns += (f'<button class="cw-scope-btn" data-scope="user:{o["name"]}">'
                 f'De {o["name"]}</button>')
    return USER_BAR.replace("__NAME__", user["name"]).replace("__OTHER_BUTTONS__", btns)


@app.get("/", response_class=HTMLResponse)
def index(session: str = Cookie(None)):
    user = _user_for_session(session)
    if not user: return RedirectResponse("/login", status_code=303)
    try:
        html = DASHBOARD_HTML_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return HTMLResponse(
            "<h1>Falta dashboard.html</h1>"
            "<p>Corré el script <code>extract_html.py</code> en el VPS para generar dashboard.html.</p>",
            status_code=500)
    bar = _build_user_bar(user)
    # User-bar: fija arriba, en todas las pantallas (justo despues de <body>).
    if "<body>" in html:
        html = html.replace("<body>", "<body>" + bar, 1)
    else:
        html = bar + html
    # Widget de vencimientos: SOLO en la tab Inicio (overview), no en todas.
    # Se inyecta dentro de <section id="overview"> para que el toggle de
    # .section (display:none/block) lo oculte cuando no estas en Inicio.
    anchor = '<div class="cards" id="overview-cards"></div>'
    if anchor in html:
        html = html.replace(anchor, anchor + VENC_WIDGET, 1)
    else:
        # fallback: si cambia el markup, no perder el widget
        html = html.replace("<body>" + bar, "<body>" + bar + VENC_WIDGET, 1)
    return HTMLResponse(html)


vencimientos.registrar_endpoint(app, str(DB_PATH), require_user, resolve_scope_uid)
