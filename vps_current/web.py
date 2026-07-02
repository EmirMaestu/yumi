"""
Dashboard web multi-usuario.
- Login con usuario/contraseña por persona (las passwords se settean con /password en el bot).
- Cada usuario ve solo SUS datos por default.
- Toggle "mías / de ella / ambos" en la barra superior.
- El HTML del dashboard se carga desde dashboard.html (separar mantiene este archivo manejable).
"""

import os
import re
import csv
import json
import hmac
import asyncio
import threading
import sqlite3
import secrets
import hashlib
import urllib.request
import urllib.parse
import time as _time
import io
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body, Request, Response, Cookie, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse, PlainTextResponse
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

@app.get("/api/health")
def health():
    return {"ok": True}


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


PBKDF2_ITERS = 200_000

def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERS).hex()
    return f"pbkdf2${PBKDF2_ITERS}${salt}${h}"

def verify_password(password, stored):
    """Acepta PBKDF2 (nuevo) y sha256 salteado (legacy) para migración gradual."""
    if not stored: return False
    if stored.startswith("pbkdf2$"):
        try:
            _, iters, salt, h = stored.split("$", 3)
            calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters)).hex()
            return secrets.compare_digest(calc, h)
        except Exception:
            return False
    if "$" not in stored: return False  # legacy: salt$sha256(salt+pw)
    salt, h = stored.split("$", 1)
    return secrets.compare_digest(hashlib.sha256((salt + password).encode()).hexdigest(), h)

def password_needs_upgrade(stored):
    return bool(stored) and not stored.startswith("pbkdf2$")


# --- Rate limiting en memoria (sliding window por clave) -----------------
_RL_HITS = {}  # key -> [timestamps]

def _client_ip(request):
    xff = request.headers.get("x-forwarded-for") if request else None
    if xff: return xff.split(",")[0].strip()
    return (request.client.host if request and request.client else "unknown")

def rate_limit(key, max_hits, window_secs):
    """True si se superó el límite (debe rechazarse)."""
    now = datetime.now().timestamp()
    bucket = [t for t in _RL_HITS.get(key, []) if now - t < window_secs]
    bucket.append(now)
    _RL_HITS[key] = bucket[-max_hits * 2:]  # acota el crecimiento
    return len(bucket) > max_hits


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


# ─── Admin ────────────────────────────────────────────────────────────────
# Admin = telegram_id en ADMIN_USER_IDS. Fallback a ALLOWED_USER_IDS (la pareja)
# para que el panel funcione ya, sin config extra. Para restringir a una sola
# persona, setear ADMIN_USER_IDS en el .env.
_admin_raw = (os.environ.get("ADMIN_USER_IDS", "").strip()
              or os.environ.get("ALLOWED_USER_IDS", "").strip()
              or os.environ.get("ALLOWED_USER_ID", "").strip())
ADMIN_USER_IDS = [int(x.strip()) for x in _admin_raw.split(",") if x.strip()]
# Topes (mismos defaults que el bot; solo para mostrarlos en el panel).
DAILY_GLOBAL_CAP_USD = float(os.environ.get("DAILY_GLOBAL_CAP_USD", "5") or 5)
FREE_DAILY_MSGS = int(os.environ.get("FREE_DAILY_MSGS", "15") or 15)
# Usuario del bot de Telegram, para armar los links de invitación (t.me/<bot>?start=<code>).
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").strip().lstrip("@")
APP_URL = os.environ.get("APP_URL", "https://asistente.emir-maestu.site/app").rstrip("/")

# WhatsApp Cloud API (Meta)
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "").strip().lstrip("+")
_WA_GRAPH = "https://graph.facebook.com/v21.0"
_wa_seen = set()  # dedupe de message ids (en memoria)


def is_admin(user):
    return bool(user) and user.get("telegram_id") in ADMIN_USER_IDS


def require_admin(user=Depends(require_user)):
    if not is_admin(user): raise HTTPException(403, "Solo administradores")
    return user


def _table_exists(conn, table):
    try:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None
    except Exception:
        return False


def _col_exists(conn, table, col):
    try:
        return any(r[1] == col for r in conn.execute(f"PRAGMA table_info({table})").fetchall())
    except Exception:
        return False


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


def _household_member_ids(uid):
    """IDs de usuarios del MISMO hogar que uid (incl. uid). Aislamiento multi-inquilino."""
    if uid is None:
        return []
    try:
        with db() as conn:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM users WHERE COALESCE(household_id,id)=(SELECT COALESCE(household_id,id) FROM users WHERE id=?)",
                (uid,)).fetchall()]
        return ids or [uid]
    except Exception:
        return [uid]


def _household_id_of(user):
    """ID canónico del hogar del usuario (COALESCE(household_id, id))."""
    try:
        hh = user["household_id"] if "household_id" in user.keys() else None
    except Exception:
        hh = None
    return hh or user["id"]


def resolve_scope_uid(scope_cookie, user):
    """Devuelve user_id a filtrar, o None = TODO MI HOGAR. Aislamiento: 'compartido' en un
    hogar de 1 sola persona = uno mismo; 'user:X' solo si X pertenece a mi hogar."""
    s = (scope_cookie or "mine").strip().lower()
    members = _household_member_ids(user["id"])
    if s in ("ours","shared","ambos","compartido","both"):
        return None if len(members) > 1 else user["id"]
    if s.startswith("user:"):
        u = get_user_by_name(s.split(":",1)[1])
        if u and u["id"] in members:
            return u["id"]
    return user["id"]


def user_filter(scope_cookie, user, alias="t"):
    """Visibilidad para TRANSACCIONES (privacidad por cuenta): propio + lo de cuentas
    compartidas / dueños con share_all. Reemplaza el viejo filtro por user_id."""
    import visibility
    uid = resolve_scope_uid(scope_cookie, user)
    m = _household_member_ids(user["id"])
    frag, params = visibility.where(user["id"], uid, m, alias=alias,
                                    shared_expr=visibility.shared_expr_tx(alias))
    return "AND " + frag, params


def user_filter_eq(scope_cookie, user, col="user_id"):
    """Filtro de HOGAR sin privacidad. SOLO para entidades fuera de alcance (ej. hábitos).
    Para entidades de privacidad usar vis_filter_item / vis_filter_recurring."""
    uid = resolve_scope_uid(scope_cookie, user)
    if uid is not None: return f"AND {col} = ?", [uid]
    m = _household_member_ids(user["id"]); ph = ",".join("?" for _ in m)
    return f"AND {col} IN ({ph})", list(m)


def vis_filter_item(scope_cookie, user, alias="", entity=None):
    """Visibilidad para ítems con columna `shared` (eventos/tareas/notas/recordatorios).
    alias="" → columnas sin prefijo (FROM tabla sin alias); alias="r" → r.user_id / r.shared.
    Si se pasa `entity` (eventos/recordatorios/...), suma el compartir POR INTEGRANTE
    (item_shares), igual que tareas/notas/listas."""
    import visibility
    uid = resolve_scope_uid(scope_cookie, user)
    m = _household_member_ids(user["id"])
    if entity:
        se = visibility.shared_expr_item_member(alias, entity, user["id"])
    else:
        se = visibility.shared_expr_item(alias) if alias else "shared=1"
    frag, params = visibility.where(user["id"], uid, m, alias=alias, shared_expr=se)
    return "AND " + frag, params


def vis_filter_recurring(scope_cookie, user, alias=""):
    """Visibilidad para recurrentes/cuotas (privacidad por cuenta, como las transacciones)."""
    import visibility
    uid = resolve_scope_uid(scope_cookie, user)
    m = _household_member_ids(user["id"])
    acc = (f"{alias}.account_id" if alias else "account_id")
    se = f"{acc} IN (SELECT id FROM accounts WHERE shared=1)"
    frag, params = visibility.where(user["id"], uid, m, alias=alias, shared_expr=se)
    return "AND " + frag, params


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
def login(request: Request, body: dict = Body(...), response: Response = None):
    ip = _client_ip(request)
    username = (body.get("username") or "").strip().lower()
    password = body.get("password") or ""
    if not username or not password:
        raise HTTPException(400, "Faltan datos")
    # Anti fuerza-bruta: por IP y por usuario.
    if rate_limit(f"login:ip:{ip}", 10, 300) or rate_limit(f"login:user:{username}", 6, 300):
        raise HTTPException(429, "Demasiados intentos. Esperá unos minutos.")
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE LOWER(username)=? AND active=1", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise HTTPException(401, "Usuario o contraseña incorrectos")
        if password_needs_upgrade(row["password_hash"]):  # migra sha256 → pbkdf2
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), row["id"])); conn.commit()
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


# ─── Push web (notificaciones) ─────────────────────────────────────────────
@app.get("/api/push/vapid-public-key")
def push_vapid_key():
    return {"key": os.environ.get("VAPID_PUBLIC_KEY", "")}


@app.post("/api/push/subscribe")
def push_subscribe(body: dict = Body(...), user=Depends(require_user)):
    sub = body.get("subscription") or body
    endpoint = sub.get("endpoint")
    keys = sub.get("keys") or {}
    p256dh = keys.get("p256dh"); auth = keys.get("auth")
    if not endpoint or not p256dh or not auth:
        raise HTTPException(400, "Suscripción inválida")
    with db() as conn:
        conn.execute(
            "INSERT INTO push_subscriptions(user_id, endpoint, p256dh, auth) VALUES (?,?,?,?) "
            "ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id, p256dh=excluded.p256dh, auth=excluded.auth",
            (user["id"], endpoint, p256dh, auth))
        conn.commit()
    return {"ok": True}


@app.post("/api/push/unsubscribe")
def push_unsubscribe(body: dict = Body(...), user=Depends(require_user)):
    endpoint = body.get("endpoint") or ""
    with db() as conn:
        conn.execute("DELETE FROM push_subscriptions WHERE endpoint=? AND user_id=?", (endpoint, user["id"]))
        conn.commit()
    return {"ok": True}


@app.post("/api/push/test")
def push_test(user=Depends(require_user)):
    try:
        import push_notify
        with db() as conn:
            n = push_notify.send_to_user(conn, [user["id"]], "🔔 Yumi", "¡Las notificaciones funcionan!", "/app/")
        return {"ok": True, "sent": n}
    except Exception as e:
        raise HTTPException(500, f"push falló: {e}")


# ─── Feed de calendario (.ics) ─────────────────────────────────────────────
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://asistente.emir-maestu.site").rstrip("/")


def _cal_token_for(conn, user_id):
    row = conn.execute("SELECT cal_token FROM users WHERE id=?", (user_id,)).fetchone()
    tok = row["cal_token"] if row and row["cal_token"] else None
    if not tok:
        tok = secrets.token_urlsafe(24)
        conn.execute("UPDATE users SET cal_token=? WHERE id=?", (tok, user_id))
        conn.commit()
    return tok


@app.get("/api/cal/url")
def cal_url(user=Depends(require_user)):
    with db() as conn:
        tok = _cal_token_for(conn, user["id"])
    return {"url": f"{PUBLIC_BASE_URL}/api/cal/{tok}.ics"}


@app.post("/api/cal/regenerate")
def cal_regenerate(user=Depends(require_user)):
    tok = secrets.token_urlsafe(24)
    with db() as conn:
        conn.execute("UPDATE users SET cal_token=? WHERE id=?", (tok, user["id"]))
        conn.commit()
    return {"url": f"{PUBLIC_BASE_URL}/api/cal/{tok}.ics"}


@app.get("/api/cal/{token}.ics")
def cal_feed(token: str):
    import calfeed
    with db() as conn:
        u = conn.execute("SELECT id FROM users WHERE cal_token=? AND active=1", (token,)).fetchone()
        if not u:
            raise HTTPException(404, "No encontrado")
        uid = u["id"]
        desde = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        eventos = [dict(r) for r in conn.execute(
            "SELECT id, title, starts_at, location, notes FROM eventos "
            "WHERE user_id=? AND substr(starts_at,1,10) >= ? ORDER BY starts_at", (uid, desde)).fetchall()]
        recs = [dict(r) for r in conn.execute(
            "SELECT id, text, remind_at, recurrence FROM recordatorios "
            "WHERE user_id=? AND substr(REPLACE(remind_at,' ','T'),1,10) >= ? ORDER BY remind_at",
            (uid, desde)).fetchall()]
    body = calfeed.build_ics(eventos, recs)
    return Response(content=body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="yumi.ics"'})


@app.get("/api/cal/{token}/rec/{rid}.ics")
def cal_event_rec(token: str, rid: int):
    """Un solo recordatorio como .ics (con su alarma) → para 'Agregar a mi calendario' en un toque."""
    import calfeed
    with db() as conn:
        u = conn.execute("SELECT id FROM users WHERE cal_token=? AND active=1", (token,)).fetchone()
        if not u:
            raise HTTPException(404, "No encontrado")
        rec = conn.execute("SELECT id, text, remind_at, recurrence FROM recordatorios WHERE id=? AND user_id=?",
                           (rid, u["id"])).fetchone()
        if not rec:
            raise HTTPException(404, "No encontrado")
        recs = [dict(rec)]
    body = calfeed.build_ics([], recs)
    return Response(content=body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="recordatorio.ics"'})


@app.get("/api/me")
def api_me(user=Depends(require_user), scope: str = Cookie("mine")):
    members = set(_household_member_ids(user["id"]))  # solo mi hogar (aislamiento)
    with db() as conn:
        all_users = [dict(r) for r in conn.execute("SELECT id,name,username,color FROM users WHERE active=1 ORDER BY id").fetchall()]
    other = [u for u in all_users if u["id"] != user["id"] and u["id"] in members]
    return {
        "id": user["id"], "name": user["name"], "username": user["username"], "color": user.get("color"),
        "scope": scope or "mine",
        "others": [{"name": u["name"], "scope_value": f"user:{u['name']}"} for u in other],
        "is_admin": is_admin(user),
        "share_all": bool(user["share_all"]) if "share_all" in user.keys() else False,
    }


@app.post("/api/set_scope")
def set_scope(body: dict = Body(...), user=Depends(require_user)):
    value = (body.get("value") or "mine").strip()
    resp = JSONResponse({"ok": True, "scope": value})
    resp.set_cookie("scope", value, max_age=int(SESSION_TTL.total_seconds()), samesite="lax", secure=True)
    return resp


# ─── Admin: usuarios, costos, uso ───────────────────────────────────────────
@app.get("/api/admin/overview")
def api_admin_overview(user=Depends(require_admin)):
    out = {
        "users_total": 0, "users_active": 0,
        "cost_today": 0.0, "cost_month": 0.0,
        "cost_today_system": 0.0, "cost_month_system": 0.0,
        "msgs_today": 0, "calls_today": 0,
        "by_model": [], "by_kind": [],
        "caps": {"daily_global_usd": DAILY_GLOBAL_CAP_USD, "free_daily_msgs": FREE_DAILY_MSGS},
        "usage_ready": False,
    }
    with db() as conn:
        try:
            out["users_total"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            out["users_active"] = conn.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
        except Exception:
            pass
        if _table_exists(conn, "api_usage"):
            out["usage_ready"] = True
            q = lambda sql: conn.execute(sql).fetchone()[0]
            out["cost_today"] = q("SELECT COALESCE(SUM(cost_usd),0) FROM api_usage WHERE date(created_at)=date('now')")
            out["cost_month"] = q("SELECT COALESCE(SUM(cost_usd),0) FROM api_usage WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now')")
            # Costo NO atribuible a un usuario (búsquedas de precio, digest, etc.) → fila "Sistema".
            out["cost_today_system"] = q("SELECT COALESCE(SUM(cost_usd),0) FROM api_usage WHERE user_id IS NULL AND date(created_at)=date('now')")
            out["cost_month_system"] = q("SELECT COALESCE(SUM(cost_usd),0) FROM api_usage WHERE user_id IS NULL AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now')")
            out["msgs_today"] = q("SELECT COUNT(*) FROM api_usage WHERE kind='parser' AND date(created_at)=date('now')")
            out["calls_today"] = q("SELECT COUNT(*) FROM api_usage WHERE date(created_at)=date('now')")
            out["by_model"] = [dict(r) for r in conn.execute(
                "SELECT model, COUNT(*) AS calls, COALESCE(SUM(input_tokens),0) AS input_tokens, "
                "COALESCE(SUM(output_tokens),0) AS output_tokens, COALESCE(SUM(cache_read),0) AS cache_read, "
                "COALESCE(SUM(cost_usd),0) AS cost_usd FROM api_usage "
                "WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now') "
                "GROUP BY model ORDER BY cost_usd DESC").fetchall()]
            out["by_kind"] = [dict(r) for r in conn.execute(
                "SELECT kind, COUNT(*) AS calls, COALESCE(SUM(cost_usd),0) AS cost_usd FROM api_usage "
                "WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now') "
                "GROUP BY kind ORDER BY cost_usd DESC").fetchall()]
    return out


@app.get("/api/admin/users")
def api_admin_users(user=Depends(require_admin)):
    with db() as conn:
        has_plan = _col_exists(conn, "users", "plan")
        plan_sel = "COALESCE(plan,'free')" if has_plan else "'free'"
        rows = [dict(r) for r in conn.execute(
            f"SELECT id, name, username, telegram_id, active, created_at, {plan_sel} AS plan "
            "FROM users ORDER BY id").fetchall()]
        usage_ready = _table_exists(conn, "api_usage")
        for r in rows:
            r["is_admin"] = r.get("telegram_id") in ADMIN_USER_IDS
            r["msgs_today"] = 0
            r["cost_month"] = 0.0
            if usage_ready:
                r["msgs_today"] = conn.execute(
                    "SELECT COUNT(*) FROM api_usage WHERE user_id=? AND kind='parser' AND date(created_at)=date('now')",
                    (r["id"],)).fetchone()[0]
                r["cost_month"] = conn.execute(
                    "SELECT COALESCE(SUM(cost_usd),0) FROM api_usage WHERE user_id=? "
                    "AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now')",
                    (r["id"],)).fetchone()[0]
    return {"users": rows, "usage_ready": usage_ready, "plans": ["free", "pareja", "pro"]}


@app.patch("/api/admin/users/{uid}")
def api_admin_user_update(uid: int, body: dict = Body(...), user=Depends(require_admin)):
    sets, vals = [], []
    if "name" in body:
        nm = (body.get("name") or "").strip()
        if not nm: raise HTTPException(400, "Nombre vacío")
        sets.append("name=?"); vals.append(nm[:60])
    if "plan" in body:
        plan = (body.get("plan") or "free").strip().lower()
        if plan not in ("free", "pareja", "pro"): raise HTTPException(400, "Plan inválido")
        sets.append("plan=?"); vals.append(plan)
    if "active" in body:
        if not body.get("active") and uid == user["id"]:
            raise HTTPException(400, "No podés desactivarte a vos mismo")
        sets.append("active=?"); vals.append(1 if body.get("active") else 0)
    if not sets: raise HTTPException(400, "Nada para actualizar")
    with db() as conn:
        if "plan" in body and not _col_exists(conn, "users", "plan"):
            raise HTTPException(409, "La columna 'plan' aún no existe; reiniciá el bot.")
        vals.append(uid)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()
    return {"ok": True}


@app.get("/api/admin/usage")
def api_admin_usage(days: int = 14, user=Depends(require_admin)):
    days = max(1, min(days, 90))
    with db() as conn:
        if not _table_exists(conn, "api_usage"):
            return {"days": [], "usage_ready": False}
        rows = [dict(r) for r in conn.execute(
            "SELECT date(created_at) AS day, COALESCE(SUM(cost_usd),0) AS cost_usd, COUNT(*) AS calls "
            "FROM api_usage WHERE created_at >= date('now', ?) GROUP BY day ORDER BY day",
            (f"-{days} days",)).fetchall()]
    return {"days": rows, "usage_ready": True}


@app.get("/api/admin/referrals")
def api_admin_referrals(user=Depends(require_admin)):
    with db() as conn:
        if not _col_exists(conn, "users", "referral_code"):
            return {"ready": False, "users": [], "bot_username": BOT_USERNAME}
        users = [dict(r) for r in conn.execute(
            "SELECT id, name, username, referral_code, referred_by, active FROM users ORDER BY id").fetchall()]
        counts = {}
        for r in conn.execute(
                "SELECT referred_by AS rb, COUNT(*) AS c FROM users "
                "WHERE referred_by IS NOT NULL GROUP BY referred_by").fetchall():
            counts[r["rb"]] = r["c"]
    names = {u["id"]: u["name"] for u in users}
    out = []
    for u in users:
        link = (f"https://t.me/{BOT_USERNAME}?start={u['referral_code']}"
                if BOT_USERNAME and u["referral_code"] else None)
        wa = None
        if WHATSAPP_NUMBER and u["referral_code"]:
            _txt = urllib.parse.quote(f"Hola! Me uno a Yumi 🌱 (codigo: {u['referral_code']})")
            wa = f"https://wa.me/{WHATSAPP_NUMBER}?text={_txt}"
        out.append({
            "id": u["id"], "name": u["name"], "username": u["username"],
            "referral_code": u["referral_code"], "invite_link": link, "invite_link_wa": wa,
            "invited_count": counts.get(u["id"], 0),
            "referred_by_name": names.get(u["referred_by"]) if u["referred_by"] else None,
        })
    return {"ready": True, "users": out, "bot_username": BOT_USERNAME}


@app.get("/api/admin/households")
def api_admin_households(user=Depends(require_admin)):
    """Usuarios agrupados por hogar (familia), con el plan del hogar, su tope y cuántos integrantes tiene."""
    try:
        import main as _m
        rank = _m.PLAN_RANK
        cap_for = lambda p: _m.plan_limits(p)["household"]
        msgs_for = lambda p: _m.plan_limits(p)["msgs"]
    except Exception:
        rank = {"free": 0, "pareja": 1, "pro": 2}
        cap_for = lambda p: {"free": 1, "pareja": 2, "pro": 6}.get(p, 1)
        msgs_for = lambda p: {"free": 15, "pareja": 150, "pro": 100000}.get(p, 15)
    with db() as conn:
        has_hh = _col_exists(conn, "users", "household_id")
        sel = "COALESCE(household_id, id)" if has_hh else "id"
        rows = [dict(r) for r in conn.execute(
            f"SELECT id, name, username, COALESCE(plan,'free') AS plan, {sel} AS hh, active "
            f"FROM users ORDER BY {sel}, id").fetchall()]
    groups, order = {}, []
    for r in rows:
        if r["hh"] not in groups:
            groups[r["hh"]] = []; order.append(r["hh"])
        groups[r["hh"]].append(r)
    out = []
    for hh in order:
        members = groups[hh]
        best = max((m["plan"] for m in members), key=lambda p: rank.get(p, 0))
        out.append({
            "household_id": hh, "plan": best, "cap": cap_for(best),
            "daily_msgs": msgs_for(best), "size": len(members),
            "members": [{"id": m["id"], "name": m["name"], "username": m["username"],
                         "plan": m["plan"], "active": m["active"]} for m in members],
        })
    return {"households": out}


# ─── WhatsApp Cloud API: webhook + envío ────────────────────────────────────
def wa_send(to, text):
    if not (WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID and to and text):
        return
    body = json.dumps({"messaging_product": "whatsapp", "to": str(to),
                       "type": "text", "text": {"body": str(text)[:4096]}}).encode()
    req = urllib.request.Request(
        f"{_WA_GRAPH}/{WHATSAPP_PHONE_NUMBER_ID}/messages", data=body, method="POST",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
    except Exception as e:
        print("wa_send fail:", e)


# Shim mínimo: hace que main.process_text (que espera update/context de Telegram)
# funcione para WhatsApp, ruteando las respuestas a wa_send.
class _WAUser:
    def __init__(self, uid, name): self.id = uid; self.first_name = name; self.username = None
class _WAMessage:
    def __init__(self, to, text): self._to = to; self.text = text; self.caption = None
    async def reply_text(self, text, **kwargs): wa_send(self._to, text)
class _WAUpdate:
    def __init__(self, uid, name, to, text):
        self.effective_user = _WAUser(uid, name); self.message = _WAMessage(to, text)
class _WAJobQueue:
    # Devuelve truthy: en WhatsApp el disparo real lo hace el watchdog (lee la DB),
    # pero schedule_reminder usa este retorno como "se agendó OK" (si fuera None,
    # el bot diría falsamente "esa fecha ya pasó" aunque sea futura).
    def run_once(self, *a, **k): return True
    def get_jobs_by_name(self, *a, **k): return []
class _WAApp:
    def __init__(self): self.job_queue = _WAJobQueue()
class _WAContext:
    def __init__(self): self.user_data = {}; self.application = _WAApp(); self.bot = None; self.args = []


def _wa_extract_code(main, text):
    for tok in re.findall(r"[A-Za-z0-9]+", text or ""):
        if 5 <= len(tok) <= 12 and main.get_user_by_referral_code(tok):
            return tok
    return None


def _wa_extract_family_code(main, text):
    m = re.search(r"fam_([A-Za-z0-9]{4,16})", text or "")
    if m and main.get_user_by_referral_code(m.group(1)):
        return m.group(1)
    return None


def _wa_process_message(main, frm, profile, mtype, text):
    # ¿Pedido de vinculación de cuenta? ("vincular <código>" generado con /vincular en Telegram).
    lm = re.search(r"vincular\s+([A-Za-z0-9]{4,12})", text or "", re.I)
    if lm:
        ok, name = main.link_whatsapp(lm.group(1), frm)
        if ok:
            wa_send(frm, f"✅ Listo {name}, vinculé este WhatsApp con tu cuenta de Yumi. "
                         "Ahora ves lo mismo acá y en Telegram.")
        else:
            wa_send(frm, "Ese código de vinculación no es válido o venció 😕 "
                         "Generá uno nuevo con /vincular en Telegram.")
        return
    user = main.get_user_by_wa(frm)
    if not user:
        # Invitación a la FAMILIA: se une al hogar del que invita (comparte todo).
        famcode = _wa_extract_family_code(main, text)
        if famcode:
            inviter = main.get_user_by_referral_code(famcode)
            if inviter:
                cap = main.plan_limits(main.household_plan(inviter["id"]))["household"]
                if len(main.household_member_ids(inviter["id"])) >= cap:
                    wa_send(frm, f"El hogar de {inviter['name']} ya está completo para su plan. Que actualice el plan para sumar a más.")
                    return
                hh = inviter.get("household_id") or inviter["id"]
                new_user, temp_pw = main.onboard_user("whatsapp", frm, profile or "Usuario", inviter["id"], household_id=hh)
                msg = (f"🎉 ¡Bienvenido/a a Yumi, {new_user['name']}! Te sumaste a la familia de {inviter['name']} "
                       "— van a compartir listas, gastos y agenda.")
                if temp_pw:
                    msg += (f"\n\n🌐 App web de Yumi: {APP_URL}\n"
                            f"Entrá con usuario {new_user['username']} y clave temporal {temp_pw} (cambiala desde la web).")
                wa_send(frm, msg)
                return
        code = _wa_extract_code(main, text)
        if code:
            referrer = main.get_user_by_referral_code(code)
            if referrer and main.can_invite(referrer):
                new_user, temp_pw = main.onboard_user("whatsapp", frm, profile or "Usuario", referrer["id"])
                msg = (f"🎉 ¡Bienvenido/a a Yumi, {new_user['name']}! Te invitó {referrer['name']}.\n\n"
                       "Soy tu asistente: mandame un gasto, una tarea o una pregunta.\n"
                       "💸 «pagué 1000 de café con débito»\n"
                       "✅ «tengo que pagar la luz»\n"
                       "📊 «cuánto gasté este mes?»")
                if temp_pw:
                    msg += (f"\n\n🌐 App web de Yumi: {APP_URL}\n"
                            f"Entrá con usuario {new_user['username']} y clave temporal {temp_pw} "
                            f"(cambiala desde la web). También podés usar todo acá por WhatsApp.")
                wa_send(frm, msg)
                return
        wa_send(frm, getattr(main, "REGISTER_MSG", "👋 Yumi es por invitación. Pedile su link a quien te invitó."))
        return
    if mtype != "text" or not (text or "").strip():
        wa_send(frm, "Por ahora te entiendo por texto 🙂 (los audios llegan pronto).")
        return
    try:
        raw_id = main.save_raw(user["telegram_id"], user.get("username") or profile or "", "whatsapp", text)
    except Exception:
        raw_id = None
    upd = _WAUpdate(user["telegram_id"], user["name"], frm, text)
    try:
        asyncio.run(main.process_text(upd, _WAContext(), text, raw_id))
    except Exception as e:
        print("wa process_text error:", e)
        wa_send(frm, "Uy, algo falló procesando eso 😕 Probá de nuevo.")


def _wa_handle(data):
    """Procesa el payload del webhook en background (fuera del request → 200 rápido a Meta)."""
    try:
        import main
    except Exception as e:
        print("wa: no pude importar main:", e); return
    try:
        for entry in data.get("entry", []):
            for ch in entry.get("changes", []):
                val = ch.get("value", {}) or {}
                contacts = val.get("contacts") or []
                profile = ((contacts[0].get("profile") or {}).get("name")) if contacts else ""
                for msg in (val.get("messages") or []):
                    mid = msg.get("id")
                    if mid and mid in _wa_seen:
                        continue
                    if mid:
                        _wa_seen.add(mid)
                        if len(_wa_seen) > 5000: _wa_seen.clear()
                    frm = msg.get("from")
                    mtype = msg.get("type")
                    text = (msg.get("text") or {}).get("body", "") if mtype == "text" else ""
                    _wa_process_message(main, frm, profile, mtype, text)
    except Exception as e:
        print("wa_handle error:", e)


@app.get("/api/whatsapp/webhook")
def wa_verify(request: Request):
    p = request.query_params
    if (WHATSAPP_VERIFY_TOKEN and p.get("hub.mode") == "subscribe"
            and p.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN):
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "verify failed")


@app.post("/api/whatsapp/webhook")
async def wa_receive(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if WHATSAPP_APP_SECRET:
        sig = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(WHATSAPP_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(403, "bad signature")
    try:
        data = json.loads(raw or b"{}")
    except Exception:
        data = {}
    background.add_task(_wa_handle, data)
    return {"ok": True}


# ─── Utils ────────────────────────────────────────────────────────────────
_RATE_TYPES = ("blue", "oficial", "mep", "cripto")

def _fetch_rate_now(rate_type):
    """Fetch sincrónico — se usa SOLO desde el hilo de fondo, NUNCA en el request
    (la resolución DNS fría puede tardar ~9s y no está acotada por el timeout del socket)."""
    try:
        req = urllib.request.Request(f"https://dolarapi.com/v1/dolares/{rate_type}",
                                     headers={"User-Agent": "Mozilla/5.0 (asistente-web)"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        rate = (data.get("compra", 0) + data.get("venta", 0)) / 2
        return rate or None
    except Exception:
        return None

def get_dolar_rate(rate_type="blue"):
    """NO bloquea el request: devuelve el valor cacheado (aunque esté algo viejo) o None.
    El fetch real lo hace `_rate_refresher` en un hilo de fondo, manteniendo la caché tibia."""
    e = _rate_cache.get(rate_type)
    return e[1] if e else None

def _rate_refresher():
    while True:
        for rt in _RATE_TYPES:
            r = _fetch_rate_now(rt)
            if r:
                _rate_cache[rt] = (_time.time(), r)
        _time.sleep(600)

threading.Thread(target=_rate_refresher, daemon=True, name="rate-refresher").start()


# ─── Overview ─────────────────────────────────────────────────────────────
@app.get("/api/overview")
def api_overview(user=Depends(require_user), scope: str = Cookie("mine")):
    now = now_local()
    mes_ini = now.strftime("%Y-%m-01")
    nowstr = now.strftime("%Y-%m-%dT%H:%M")
    uf_t, uf_p = user_filter(scope, user, "t")
    uf_x, uf_xp = vis_filter_item(scope, user)
    scope_uid = resolve_scope_uid(scope, user)
    acc_filter, acc_params = vis_filter_item(scope, user)  # cuentas: visibilidad por `shared` (accounts tiene la columna)

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
                    f"FROM recurring WHERE active=1 AND account_id=?",
                    [a['id']]).fetchall()
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
    uf_x, uf_xp = vis_filter_item(scope, user)
    scope_uid = resolve_scope_uid(scope, user)
    acc_filter, acc_params = vis_filter_item(scope, user)  # cuentas: visibilidad por `shared` (accounts tiene la columna)

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
                 f"WHERE t.type=? AND t.kind='normal' AND t.occurred_at>=? {uf_t}")
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
            f"WHERE t.occurred_at>=? AND t.kind='normal' {uf_t} "
            f"GROUP BY ym, t.type, t.currency", [first] + uf_p).fetchall():
            d = cf.setdefault(r["ym"], {"ingresos": 0, "gastos": 0})
            d["ingresos" if r["type"] == "ingreso" else "gastos"] += ars(r["s"], r["currency"])
        cashflow = [{"ym": k, **v} for k, v in sorted(cf.items())][-6:]

        hoy_items = []
        for r in conn.execute(
            f"SELECT id,title,starts_at,location FROM eventos WHERE substr(starts_at,1,10)=? {uf_x} ORDER BY starts_at",
            [hoy] + uf_xp).fetchall():
            # horas en que el evento te avisa (sus recordatorios), para mostrar un badge
            avisos = [rr["t"].replace(' ', 'T')[11:16] for rr in conn.execute(
                "SELECT remind_at AS t FROM recordatorios WHERE event_id=? AND fired=0 ORDER BY remind_at",
                (r["id"],)).fetchall()]
            hoy_items.append({"tipo": "evento", "titulo": r["title"], "sub": r["location"] or "",
                              "hora": r["starts_at"][11:16], "avisos": avisos})
        # Solo recordatorios SUELTOS (los de un evento se muestran como badge en el evento, no sueltos)
        for r in conn.execute(
            f"SELECT id,text,remind_at FROM recordatorios WHERE fired=0 AND event_id IS NULL AND substr(REPLACE(remind_at,' ','T'),1,10)=? {uf_x} ORDER BY remind_at",
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
            f"WHERE t.occurred_at>=? AND t.type='gasto' AND t.currency='ARS' AND t.kind='normal' {uf_t} "
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
        _vf, _vp = vis_filter_item(scope, user)  # cuentas visibles: propias + compartidas + share_all del dueño
        conds.append(_vf[4:]); params.extend(_vp)  # _vf empieza con "AND "; acá va como una condición más
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
        if "shared" in body: fields.append("shared=?"); params.append(1 if body["shared"] else 0)
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


# ─── Privacidad: compartir ítems / interruptor maestro ─────────────────────
_SHARE_ENTITIES = ("eventos", "tareas", "notas", "recordatorios", "accounts", "lists")
_PER_MEMBER_ENTITIES = ("tareas", "notas", "lists", "eventos", "recordatorios")  # soportan compartir por integrante


def _share_state(conn, entity, iid):
    """Estado actual de compartido: {shared:0|1, members:[ids]}."""
    sh = conn.execute(f"SELECT COALESCE(shared,0) FROM {entity} WHERE id=?", (iid,)).fetchone()
    mem = [r[0] for r in conn.execute(
        "SELECT shared_with_user_id FROM item_shares WHERE entity=? AND item_id=? ORDER BY shared_with_user_id",
        (entity, iid)).fetchall()]
    return {"shared": (sh[0] if sh else 0), "members": mem}


@app.post("/api/share")
def api_set_shared(body: dict = Body(...), user=Depends(require_user)):
    """Configura el compartido de un ítem. SOLO el dueño.
    body: {entity, id, shared?:0|1, members?:[user_id]}.
    - `shared=1` → visible para TODO el hogar; `shared=0` → privado (salvo per-member).
    - `members` (solo tareas/notas/lists) → REEMPLAZA con quiénes se comparte puntualmente
      (validados: del mismo hogar y distintos del dueño)."""
    entity = (body.get("entity") or "").strip()
    iid = body.get("id")
    if entity not in _SHARE_ENTITIES:
        raise HTTPException(400, "entity inválida")
    owner_col = "owner_user_id" if entity == "lists" else "user_id"
    members_in = body.get("members")
    with db() as conn:
        row = conn.execute(f"SELECT {owner_col} AS o FROM {entity} WHERE id=?", (iid,)).fetchone()
        if not row: raise HTTPException(404, "No existe")
        if row["o"] != user["id"]: raise HTTPException(403, "No es tuyo")
        if "shared" in body:
            conn.execute(f"UPDATE {entity} SET shared=? WHERE id=?", (1 if body.get("shared") else 0, iid))
        if members_in is not None and entity in _PER_MEMBER_ENTITIES:
            hh = set(_household_member_ids(user["id"]))
            valid = sorted({int(m) for m in members_in
                            if str(m).lstrip("-").isdigit() and int(m) in hh and int(m) != user["id"]})
            conn.execute("DELETE FROM item_shares WHERE entity=? AND item_id=?", (entity, iid))
            for mi in valid:
                conn.execute(
                    "INSERT OR IGNORE INTO item_shares(entity,item_id,owner_user_id,shared_with_user_id) "
                    "VALUES (?,?,?,?)", (entity, iid, user["id"], mi))
        conn.commit()
        state = _share_state(conn, entity, iid)
    return {"ok": True, **state}


@app.get("/api/share")
def api_get_shared(entity: str, id: int, user=Depends(require_user)):
    """Estado de compartido de un ítem (para prefilar la UI). SOLO el dueño."""
    entity = (entity or "").strip()
    if entity not in _SHARE_ENTITIES:
        raise HTTPException(400, "entity inválida")
    owner_col = "owner_user_id" if entity == "lists" else "user_id"
    with db() as conn:
        row = conn.execute(f"SELECT {owner_col} AS o FROM {entity} WHERE id=?", (id,)).fetchone()
        if not row: raise HTTPException(404, "No existe")
        if row["o"] != user["id"]: raise HTTPException(403, "No es tuyo")
        return _share_state(conn, entity, id)


@app.get("/api/household/members")
def api_household_members(user=Depends(require_user)):
    """Integrantes del hogar (para el selector de compartir). Incluye al propio (is_me)."""
    members = _household_member_ids(user["id"])
    if not members:
        return []
    ph = ",".join("?" for _ in members)
    with db() as conn:
        rows = conn.execute(
            f"SELECT id, name, color FROM users WHERE id IN ({ph}) AND active=1 ORDER BY id", members).fetchall()
    return [{"id": r["id"], "name": r["name"], "color": r["color"], "is_me": r["id"] == user["id"]} for r in rows]


@app.post("/api/settings/share_all")
def api_set_share_all(body: dict = Body(...), user=Depends(require_user)):
    """Interruptor maestro: compartir TODO lo mío con mi hogar (1) o nada por default (0)."""
    val = 1 if body.get("value") else 0
    with db() as conn:
        conn.execute("UPDATE users SET share_all=? WHERE id=?", (val, user["id"])); conn.commit()
    return {"ok": True, "share_all": val}


# ─── Categories (por hogar; household_id NULL = compartida/default) ─────────
# Las categorías default vienen con household_id NULL → visibles para todos, NO
# editables. Cada hogar puede crear/editar/borrar SOLO las suyas (A-3).
@app.get("/api/categories")
def api_categories(include_inactive: bool = False, user=Depends(require_user)):
    hh = _household_id_of(user)
    q = "SELECT * FROM categories WHERE (household_id IS NULL OR household_id=?)"
    if not include_inactive: q += " AND active=1"
    q += " ORDER BY active DESC, type, name"
    with db() as conn:
        rows = conn.execute(q, (hh,)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/categories")
def api_cat_create(body: dict = Body(...), user=Depends(require_user)):
    name = (body.get("name") or "").strip()
    if not name: raise HTTPException(400, "Nombre requerido")
    hh = _household_id_of(user)
    with db() as conn:
        # único dentro del hogar (y no pisar una compartida del mismo nombre)
        if conn.execute("SELECT id FROM categories WHERE name=? AND (household_id=? OR household_id IS NULL)",
                        (name, hh)).fetchone():
            raise HTTPException(400, "Ya existe")
        cur = conn.execute("INSERT INTO categories (name,type,color,icon,active,household_id) VALUES (?,?,?,?,1,?)",
            (name, body.get("type","gasto"), body.get("color","#94a3b8"), body.get("icon","📦"), hh))
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


def _own_category_or_403(conn, cid, user):
    """Devuelve la fila si la categoría es del hogar del usuario; si es compartida
    (household_id NULL) o de otro hogar, tira 403; si no existe, 404."""
    row = conn.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone()
    if not row: raise HTTPException(404, "No existe")
    if row["household_id"] is None:
        # Las categorías default (compartidas por todos) solo las cura el admin.
        if is_admin(user): return row
        raise HTTPException(403, "Categoría compartida (no editable)")
    if row["household_id"] != _household_id_of(user): raise HTTPException(403, "No es de tu hogar")
    return row


@app.patch("/api/categories/{cid}")
def api_cat_update(cid: int, body: dict = Body(...), user=Depends(require_user)):
    fields=[]; params=[]
    for k in ("name","type","color","icon"):
        if k in body: fields.append(f"{k}=?"); params.append(body[k])
    if "active" in body: fields.append("active=?"); params.append(1 if body["active"] else 0)
    if not fields: raise HTTPException(400, "Sin cambios")
    with db() as conn:
        _own_category_or_403(conn, cid, user)
        params.append(cid)
        conn.execute(f"UPDATE categories SET {', '.join(fields)} WHERE id=?", params); conn.commit()
    return {"ok": True}


@app.delete("/api/categories/{cid}")
def api_cat_delete(cid: int, user=Depends(require_user)):
    with db() as conn:
        _own_category_or_403(conn, cid, user)
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
    # kind: solo 'normal' (default) y 'adjustment' por acá; transfer/card_payment van por /api/transfers.
    kind = body.get("kind", "normal")
    if kind not in ("normal", "adjustment"):
        raise HTTPException(400, "Usá /api/transfers")
    with db() as conn:
        # validar que la cuenta sea del usuario
        acc = conn.execute("SELECT user_id FROM accounts WHERE id=?", (int(body["account_id"]),)).fetchone()
        if not acc: raise HTTPException(400, "Cuenta inexistente")
        if acc["user_id"] != user["id"]: raise HTTPException(403, "Esa cuenta no es tuya")
        cur = conn.execute(
            "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,user_id,kind) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (body["type"], float(body["amount"]), body.get("currency","ARS"),
             int(body["account_id"]), int(body["category_id"]) if body.get("category_id") else None,
             body.get("description"), body["occurred_at"], user["id"], kind))
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
    uf_x, uf_xp = vis_filter_recurring(scope, user, alias="r")
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
    uf_x, uf_xp = vis_filter_item(scope, user, entity="eventos")
    sc = "(SELECT COUNT(*) FROM item_shares s WHERE s.entity='eventos' AND s.item_id=eventos.id) AS share_count"
    nowstr = now_local().strftime("%Y-%m-%dT%H:%M")
    with db() as conn:
        if past:
            rows = conn.execute(f"SELECT *, {sc} FROM eventos WHERE starts_at<? {uf_x} ORDER BY starts_at DESC LIMIT 50",
                                [nowstr] + uf_xp).fetchall()
        else:
            rows = conn.execute(f"SELECT *, {sc} FROM eventos WHERE starts_at>=? {uf_x} ORDER BY starts_at ASC",
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
        conn.execute("DELETE FROM eventos WHERE id=?", (eid,))
        conn.execute("DELETE FROM item_shares WHERE entity='eventos' AND item_id=?", (eid,)); conn.commit()
    return {"ok": True}


@app.get("/api/tareas")
def api_tareas(status: str = "pendiente", user=Depends(require_user), scope: str = Cookie("mine")):
    # Visibilidad central (hogar): propias + compartidas (con el hogar, share_all del
    # dueño, o per-member conmigo). Reemplaza el filtro inline previo, que en scope
    # "ours" hacía 1=1 (fuga entre hogares) y en otros mostraba cualquier shared=1.
    import visibility
    scope_uid = resolve_scope_uid(scope, user)
    members = _household_member_ids(user["id"])
    se = visibility.shared_expr_item_member("", "tareas", user["id"])
    frag, vp = visibility.where(user["id"], scope_uid, members, alias="", shared_expr=se)
    sc = "(SELECT COUNT(*) FROM item_shares s WHERE s.entity='tareas' AND s.item_id=tareas.id) AS share_count"
    with db() as conn:
        if status == "all":
            rows = conn.execute(
                f"SELECT *, {sc} FROM tareas WHERE {frag} ORDER BY created_at DESC LIMIT 200", vp).fetchall()
        else:
            rows = conn.execute(
                f"SELECT *, {sc} FROM tareas WHERE status=? AND {frag} ORDER BY "
                f"CASE priority WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, "
                f"COALESCE(due_at,'9999'), id", [status] + vp).fetchall()
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


def _can_touch_shared(conn, row, user):
    """True si la fila (user_id, sh) es del usuario, o compartida y de su hogar."""
    if not row: return False
    if row["user_id"] == user["id"]: return True
    return bool(row["sh"]) and row["user_id"] in _household_member_ids(user["id"])


@app.post("/api/tareas/{tid}/done")
def t_done(tid: int, user=Depends(require_user)):
    import visibility
    with db() as conn:
        if not conn.execute("SELECT 1 FROM tareas WHERE id=?", (tid,)).fetchone(): raise HTTPException(404, "No existe")
        # Marcar hecha = colaborar (dueño o con quien esté compartida).
        if not visibility.can_collaborate(conn, "tareas", tid, user["id"]): raise HTTPException(403, "No es tuya")
        conn.execute("UPDATE tareas SET status='hecha', completed_at=datetime('now') WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.post("/api/tareas/{tid}/undone")
def t_undone(tid: int, user=Depends(require_user)):
    import visibility
    with db() as conn:
        if not conn.execute("SELECT 1 FROM tareas WHERE id=?", (tid,)).fetchone(): raise HTTPException(404, "No existe")
        if not visibility.can_collaborate(conn, "tareas", tid, user["id"]): raise HTTPException(403, "No es tuya")
        conn.execute("UPDATE tareas SET status='pendiente', completed_at=NULL WHERE id=?", (tid,)); conn.commit()
    return {"ok": True}


@app.delete("/api/tareas/{tid}")
def del_tar(tid: int, user=Depends(require_user)):
    import visibility
    with db() as conn:
        if not conn.execute("SELECT 1 FROM tareas WHERE id=?", (tid,)).fetchone(): raise HTTPException(404, "No existe")
        # Borrar = SOLO el dueño (aunque esté compartida).
        if not visibility.is_owner(conn, "tareas", tid, user["id"]): raise HTTPException(403, "Solo el dueño puede borrar")
        conn.execute("DELETE FROM tareas WHERE id=?", (tid,))
        conn.execute("DELETE FROM item_shares WHERE entity='tareas' AND item_id=?", (tid,)); conn.commit()
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
    uf_x, uf_xp = vis_filter_item(scope, user, entity="recordatorios")
    sc = "(SELECT COUNT(*) FROM item_shares s WHERE s.entity='recordatorios' AND s.item_id=recordatorios.id) AS share_count"
    with db() as conn:
        if include_fired:
            rows = conn.execute(f"SELECT *, {sc} FROM recordatorios WHERE 1=1 {uf_x} ORDER BY remind_at DESC LIMIT 100", uf_xp).fetchall()
        else:
            rows = conn.execute(f"SELECT *, {sc} FROM recordatorios WHERE fired=0 {uf_x} ORDER BY remind_at ASC", uf_xp).fetchall()
    return [dict(r) for r in rows]


@app.delete("/api/recordatorios/{rid}")
def del_rec(rid: int, user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM recordatorios WHERE id=?", (rid,)).fetchone()
        if row and row["user_id"] != user["id"]: raise HTTPException(403, "No es tuyo")
        conn.execute("DELETE FROM recordatorios WHERE id=?", (rid,))
        conn.execute("DELETE FROM item_shares WHERE entity='recordatorios' AND item_id=?", (rid,)); conn.commit()
    return {"ok": True}


@app.get("/api/notas")
def api_notas(q: str = None, limit: int = 50, user=Depends(require_user), scope: str = Cookie("mine")):
    # Visibilidad central (hogar): propias + compartidas (con el hogar o per-member).
    # Antes, scope "ours" mostraba TODAS las notas del hogar (incl. privadas ajenas).
    import visibility
    scope_uid = resolve_scope_uid(scope, user)
    members = _household_member_ids(user["id"])
    se = visibility.shared_expr_item_member("", "notas", user["id"])
    frag, vp = visibility.where(user["id"], scope_uid, members, alias="", shared_expr=se)
    sc = "(SELECT COUNT(*) FROM item_shares s WHERE s.entity='notas' AND s.item_id=notas.id) AS share_count"
    with db() as conn:
        if q:
            rows = conn.execute(
                f"SELECT *, {sc} FROM notas WHERE text LIKE ? AND {frag} ORDER BY created_at DESC LIMIT ?",
                [f"%{q}%"] + vp + [limit]).fetchall()
        else:
            rows = conn.execute(
                f"SELECT *, {sc} FROM notas WHERE {frag} ORDER BY created_at DESC LIMIT ?",
                vp + [limit]).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/notas")
def crear_nota(body: dict = Body(...), user=Depends(require_user)):
    text = (body.get("text") or "").strip()
    if not text: raise HTTPException(400, "Texto requerido")
    tags = json.dumps(body.get("tags") or [], ensure_ascii=False)
    desc = (body.get("description") or "").strip() or None
    with db() as conn:
        cur = conn.execute("INSERT INTO notas (text,tags,description,user_id) VALUES (?,?,?,?)",
                           (text, tags, desc, user["id"])); conn.commit()
    return {"id": cur.lastrowid, "ok": True}


@app.delete("/api/notas/{nid}")
def del_nota(nid: int, user=Depends(require_user)):
    import visibility
    with db() as conn:
        if not conn.execute("SELECT 1 FROM notas WHERE id=?", (nid,)).fetchone(): raise HTTPException(404, "No existe")
        # Borrar = SOLO el dueño (editar el texto sí puede el que colabora, vía PATCH).
        if not visibility.is_owner(conn, "notas", nid, user["id"]): raise HTTPException(403, "Solo el dueño puede borrar")
        conn.execute("DELETE FROM notas WHERE id=?", (nid,))
        conn.execute("DELETE FROM item_shares WHERE entity='notas' AND item_id=?", (nid,)); conn.commit()
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
    uf_x, uf_xp = vis_filter_recurring(scope, user)
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
    # Patrimonio es PERSONAL bajo el modelo de privacidad: cada uno ve solo el suyo
    # (no exponemos el patrimonio del otro integrante del hogar).
    with db() as conn:
        rows = conn.execute(
            "SELECT substr(taken_at,1,10) AS day, total_ars, total_usd "
            "FROM net_worth_snapshots WHERE user_id=? ORDER BY taken_at", (user["id"],)).fetchall()
    series = [{"day": r["day"], "total_ars": r["total_ars"], "total_usd": r["total_usd"]} for r in rows]

    # punto "ahora" en vivo (no persiste; solo para el grafico/encabezado)
    now_point = None
    try:
        balances = _web_account_balances(user["id"])  # patrimonio personal (solo mis cuentas)
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
                f"AND t.kind='normal' {uf_t} "
                f"GROUP BY ym, cat, t.currency", [first] + uf_p).fetchall()]
            return trends.bucket_by_category(rows, months=months, today=today, currency=currency)
        rows = [dict(r) for r in conn.execute(
            f"SELECT substr(t.occurred_at,1,7) AS ym, t.type, t.currency, SUM(t.amount) AS total "
            f"FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            f"WHERE t.occurred_at>=? AND t.kind='normal' {uf_t} "
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
    uf_rec, uf_recp = vis_filter_recurring(scope, user)   # recurrentes/cuotas: por cuenta
    uf_item, uf_itemp = vis_filter_item(scope, user)      # eventos/recordatorios: por ítem
    uf_acc, uf_accp = vis_filter_item(scope, user)        # cuentas: por `shared` (accounts tiene shared)
    scope_uid = resolve_scope_uid(scope, user)
    pagos = []
    agenda = []
    with db() as conn:
        # --- PAGOS: recurrentes ---
        for r in conn.execute(
            f"SELECT description, amount, currency, next_occurrence "
            f"FROM recurring WHERE active=1 AND next_occurrence<=? {uf_rec} "
            f"ORDER BY next_occurrence", [horizon] + uf_recp).fetchall():
            pagos.append({"date": r["next_occurrence"][:10], "kind": "recurrente",
                          "title": r["description"], "amount": r["amount"], "currency": r["currency"]})
        # --- AGENDA: eventos (vida) ---
        for r in conn.execute(
            f"SELECT title, starts_at, location FROM eventos "
            f"WHERE starts_at>=? AND substr(starts_at,1,10)<=? {uf_item} ORDER BY starts_at",
            [nowstr, horizon] + uf_itemp).fetchall():
            agenda.append({"date": r["starts_at"][:10], "datetime": r["starts_at"],
                           "kind": "evento", "title": r["title"],
                           "sub": r["location"] or "", "amount": None, "currency": None})
        # --- AGENDA: recordatorios (vida) ---
        for r in conn.execute(
            f"SELECT text, REPLACE(remind_at,' ','T') AS ra FROM recordatorios "
            f"WHERE fired=0 AND REPLACE(remind_at,' ','T')<=? {uf_item} ORDER BY ra",
            [horizon + "T23:59"] + uf_itemp).fetchall():
            agenda.append({"date": r["ra"][:10], "datetime": r["ra"],
                           "kind": "recordatorio", "title": r["text"],
                           "sub": "", "amount": None, "currency": None})
        cards = conn.execute(
            f"SELECT * FROM accounts WHERE type='credito' AND active=1 {uf_acc}", uf_accp).fetchall()
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
