import os
import re
import json
import base64
import sqlite3
import calendar
import difflib
import unicodedata
import logging
import hashlib
import secrets
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from anthropic import Anthropic
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# # >>> vencimientos patch
import vencimientos
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from contextlib import contextmanager
import asyncio
import fx
import networth
import splits
import finance
import conversation
import compare
import affordability
import digest
import proactive
import recurrence
import streaks
import shopping

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TIMEZONE = os.environ.get("TIMEZONE", "America/Argentina/Buenos_Aires")

_allowed_raw = (os.environ.get("ALLOWED_USER_IDS", "").strip()
                or os.environ.get("ALLOWED_USER_ID", "").strip())
ALLOWED_USER_IDS = [int(x.strip()) for x in _allowed_raw.split(",") if x.strip()]
APP_URL = os.environ.get("APP_URL", "https://asistente.emir-maestu.site/app").rstrip("/")

DB_PATH = BASE_DIR / "data.db"

@contextmanager
def db():
    """Conexion SQLite (row_factory + busy_timeout, commit/close garantizados). Para CODIGO NUEVO de features."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def _takenos_manual():
    """Valor manual del dolar Takenos si el usuario lo seteo (user_settings); si no, None -> cae a 'cripto'."""
    try:
        with db() as c:
            r = c.execute("SELECT value FROM user_settings WHERE key=? ORDER BY user_id LIMIT 1",
                          (fx.TAKENOS_RATE_KEY,)).fetchone()
        return float(r["value"]) if r and r["value"] else None
    except Exception:
        return None

def convert_fx(amount, from_cur, to_cur, rate_type="blue", explicit_rate=None):
    """Wrapper de fx.convert: inyecta get_dolar_rate y el rate Takenos manual. Usar en TODA conversion de features."""
    return fx.convert(amount, from_cur, to_cur, get_dolar_rate, rate_type, explicit_rate, _takenos_manual())

VOICE_DIR = BASE_DIR / "voice"; VOICE_DIR.mkdir(exist_ok=True)
PHOTO_DIR = BASE_DIR / "photos"; PHOTO_DIR.mkdir(exist_ok=True)
TZ = ZoneInfo(TIMEZONE)
MODEL = "claude-haiku-4-5-20251001"
MODEL_SMART = "claude-sonnet-4-6"
WHISPER_MODEL_SIZE = "base"
EVENT_REMINDER_MIN = 30
RECURRING_HOUR = 8

PENDING_OPS = {}

import urllib.request
import time as _time

_rate_cache = {}
RATE_TTL = 900

# # >>> photo cuotas patch
# # >>> photo cuotas v3
# # >>> photo cuotas v4
# # >>> photo cuotas v5
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Cost tracking (precios aprox. USD por 1M tokens) ──────────────────────────
_PRICING = {
    "claude-haiku-4-5-20251001": {"in": 1.0, "out": 5.0},
    "claude-sonnet-4-6": {"in": 3.0, "out": 15.0},
}
_PRICING_DEFAULT = {"in": 3.0, "out": 15.0}

def _log_usage(resp, user_id, model, kind):
    """Registra tokens/costo de una llamada a Claude. Nunca debe romper el flujo."""
    try:
        u = getattr(resp, "usage", None)
        if not u:
            return
        it = getattr(u, "input_tokens", 0) or 0
        ot = getattr(u, "output_tokens", 0) or 0
        cr = getattr(u, "cache_read_input_tokens", 0) or 0
        cw = getattr(u, "cache_creation_input_tokens", 0) or 0
        p = _PRICING.get(model, _PRICING_DEFAULT)
        cost = (it * p["in"] + ot * p["out"] + cr * p["in"] * 0.1 + cw * p["in"] * 1.25) / 1_000_000
        # Cargo aparte del web_search (no son tokens): ~US$10 / 1000 búsquedas.
        st = getattr(u, "server_tool_use", None)
        ws = (getattr(st, "web_search_requests", 0) or 0) if st else 0
        cost += ws * 0.01
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO api_usage(user_id,model,kind,input_tokens,output_tokens,cache_read,cache_write,cost_usd) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, model, kind, it, ot, cr, cw, round(cost, 6)))
        conn.commit(); conn.close()
    except Exception:
        log.exception("log_usage fallo (no critico)")

# ── Controles de costo ────────────────────────────────────────────────────────
DAILY_GLOBAL_CAP_USD = float(os.environ.get("DAILY_GLOBAL_CAP_USD", "5") or 5)
FREE_DAILY_MSGS = int(os.environ.get("FREE_DAILY_MSGS", "15") or 15)
# Búsqueda de precios online (web_search): es lo más caro del bot. Se puede apagar
# con PRECIO_ENABLED=0 en el .env (default: prendido).
PRECIO_ENABLED = (os.environ.get("PRECIO_ENABLED", "1") or "1").strip().lower() not in ("0", "false", "no", "off")

# ── Planes (límites por plan; los beneficios aplican al HOGAR, no al usuario) ──
PLAN_RANK = {"free": 0, "pareja": 1, "pro": 2}
PLAN_LIMITS = {
    "free":   {"msgs": FREE_DAILY_MSGS, "household": 1},
    "pareja": {"msgs": int(os.environ.get("PAREJA_DAILY_MSGS", "150") or 150), "household": 2},
    "pro":    {"msgs": int(os.environ.get("PRO_DAILY_MSGS", "100000") or 100000),
               "household": int(os.environ.get("PRO_HOUSEHOLD", "6") or 6)},
}

def plan_limits(plan):
    return PLAN_LIMITS.get((plan or "free").strip().lower(), PLAN_LIMITS["free"])

def household_plan(user_id):
    """Mejor plan del hogar (free<pareja<pro). Define quota de mensajes y tope de miembros
    para TODO el hogar (un miembro pago hace que toda la familia tenga el beneficio)."""
    try:
        ids = household_member_ids(user_id)
        if not ids:
            return _user_plan(user_id)
        conn = sqlite3.connect(DB_PATH)
        ph = ",".join("?" for _ in ids)
        plans = [(r[0] or "free") for r in conn.execute(f"SELECT plan FROM users WHERE id IN ({ph})", ids).fetchall()]
        conn.close()
        return max(plans, key=lambda p: PLAN_RANK.get(p, 0)) if plans else "free"
    except Exception:
        return _user_plan(user_id)

def _today_cost_usd():
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) FROM api_usage WHERE date(created_at)=date('now')"
        ).fetchone()
        conn.close()
        return float(row[0] or 0)
    except Exception:
        return 0.0

def _user_plan(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT plan FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        return (row[0] if row and row[0] else "free")
    except Exception:
        return "free"

def _user_msgs_today(user_id):
    """Cuenta mensajes (llamadas al parser Haiku) de un usuario hoy."""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT COUNT(*) FROM api_usage WHERE user_id=? AND kind='parser' "
            "AND date(created_at)=date('now')", (user_id,)).fetchone()
        conn.close()
        return int(row[0] or 0)
    except Exception:
        return 0

def cost_gate(user_id):
    """Devuelve un mensaje si hay que frenar al usuario, o None si puede seguir.
    Fail-open: si cualquier chequeo falla, dejamos pasar (nunca bloquear por un bug)."""
    try:
        if _today_cost_usd() >= DAILY_GLOBAL_CAP_USD:
            log.warning("TOPE GLOBAL diario alcanzado (US$%.2f). Pausando.", DAILY_GLOBAL_CAP_USD)
            return "Llegamos al límite de uso de hoy 😴 Probá de nuevo mañana."
        plan = household_plan(user_id)
        limit = plan_limits(plan)["msgs"]
        if _user_msgs_today(user_id) >= limit:
            extra = " Pasate a un plan superior para enviar más." if plan == "free" else ""
            return f"Llegaste a los {limit} mensajes de hoy (plan {plan}) 🙌 Mañana se renueva.{extra}"
    except Exception:
        log.exception("cost_gate fallo (dejo pasar)")
    return None
MESES_ES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
DIAS_ES = ["lun","mar","mié","jue","vie","sáb","dom"]
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
log = logging.getLogger("asistente")

_whisper = None
def get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        log.info("Cargando Whisper %s...", WHISPER_MODEL_SIZE)
        _whisper = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper

def now_local(): return datetime.now(TZ)
def parse_local(s):
    if 'T' not in s: s += "T00:00"
    return datetime.fromisoformat(s).replace(tzinfo=TZ)


PBKDF2_ITERS = 200_000

def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERS).hex()
    return f"pbkdf2${PBKDF2_ITERS}${salt}${h}"

def verify_password(password, stored):
    """Acepta PBKDF2 (nuevo) y sha256 salteado (legacy)."""
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


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            color TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS raw_messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER NOT NULL, tg_username TEXT, kind TEXT NOT NULL, content TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'efectivo',
            color TEXT, icon TEXT, active INTEGER NOT NULL DEFAULT 1,
            user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE, type TEXT NOT NULL DEFAULT 'gasto',
            color TEXT, icon TEXT, active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL DEFAULT 'gasto', amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'ARS',
            account_id INTEGER NOT NULL, category_id INTEGER,
            description TEXT, occurred_at TEXT NOT NULL,
            recurring_id INTEGER, raw_message_id INTEGER,
            user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS recurring (id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL DEFAULT 'gasto', amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'ARS',
            account_id INTEGER NOT NULL, category_id INTEGER,
            description TEXT NOT NULL,
            frequency TEXT NOT NULL DEFAULT 'monthly',
            day_of_month INTEGER, next_occurrence TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            total_installments INTEGER,
            installments_fired INTEGER NOT NULL DEFAULT 0,
            raw_message_id INTEGER,
            user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS eventos (id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, starts_at TEXT NOT NULL, location TEXT, notes TEXT,
            raw_message_id INTEGER, user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS recordatorios (id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL, remind_at TEXT NOT NULL, fired INTEGER NOT NULL DEFAULT 0,
            source TEXT, raw_message_id INTEGER, user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS tareas (id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'media', due_at TEXT,
            status TEXT NOT NULL DEFAULT 'pendiente', completed_at TEXT,
            raw_message_id INTEGER, user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS habito_logs (id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, value REAL, unit TEXT, note TEXT,
            logged_at TEXT NOT NULL DEFAULT (datetime('now')), raw_message_id INTEGER, user_id INTEGER);
        CREATE TABLE IF NOT EXISTS notas (id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL, tags TEXT, raw_message_id INTEGER, user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE INDEX IF NOT EXISTS idx_tx_occ ON transactions(occurred_at);
        CREATE INDEX IF NOT EXISTS idx_tx_acc ON transactions(account_id);
        CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_tx_user_occ ON transactions(user_id, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_tx_cat ON transactions(category_id);
        CREATE INDEX IF NOT EXISTS idx_users_tg ON users(telegram_id);
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT,
            PRIMARY KEY (user_id, key));
        CREATE TABLE IF NOT EXISTS shared_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payer_user_id INTEGER NOT NULL, other_user_id INTEGER NOT NULL,
            amount REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'ARS',
            other_share REAL NOT NULL, description TEXT, occurred_at TEXT NOT NULL,
            transaction_id INTEGER, settled_at TEXT, raw_message_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS savings_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, name TEXT NOT NULL,
            target_amount REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'USD',
            current_amount REAL NOT NULL DEFAULT 0, deadline TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS shopping_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, shared INTEGER NOT NULL DEFAULT 1,
            text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')), done_at TEXT);
        CREATE TABLE IF NOT EXISTS fx_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, rate_type TEXT NOT NULL DEFAULT 'cripto',
            direction TEXT NOT NULL, threshold REAL NOT NULL,
            active INTEGER NOT NULL DEFAULT 1, last_fired_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS net_worth_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, taken_at TEXT NOT NULL,
            total_ars REAL, total_usd REAL, detail_json TEXT);
        CREATE TABLE IF NOT EXISTS category_learning (
            user_id INTEGER NOT NULL, keyword TEXT NOT NULL,
            category_id INTEGER NOT NULL, count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (user_id, keyword, category_id));
        CREATE INDEX IF NOT EXISTS idx_se_payer ON shared_expenses(payer_user_id, settled_at);
        CREATE INDEX IF NOT EXISTS idx_se_other ON shared_expenses(other_user_id, settled_at);
        CREATE INDEX IF NOT EXISTS idx_nws_user ON net_worth_snapshots(user_id, taken_at);
        CREATE INDEX IF NOT EXISTS idx_recordatorios_pend ON recordatorios(fired, remind_at);
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, kind TEXT, icon TEXT,
            owner_user_id INTEGER, shared INTEGER NOT NULL DEFAULT 1,
            target_date TEXT, recurrence TEXT, is_template INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS event_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL, file_id TEXT NOT NULL, kind TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE INDEX IF NOT EXISTS idx_evatt_ev ON event_attachments(event_id);
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, model TEXT, kind TEXT,
            input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
            cache_read INTEGER DEFAULT 0, cache_write INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE INDEX IF NOT EXISTS idx_api_usage_created ON api_usage(created_at);
        CREATE INDEX IF NOT EXISTS idx_api_usage_user ON api_usage(user_id, created_at);
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL, auth TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE INDEX IF NOT EXISTS idx_push_user ON push_subscriptions(user_id);
    """)
    for tbl in ("accounts","transactions","recurring","eventos","recordatorios","tareas","habito_logs","notas"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if "user_id" not in cols:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER")
    # columnas nuevas para las features (idempotente; closing_day/due_day ya pueden existir por migrate_tarjetas.py)
    _ALTERS = {
        "users": [("plan", "TEXT DEFAULT 'free'"),
                  ("referral_code", "TEXT"),
                  ("referred_by", "INTEGER"),
                  ("channel", "TEXT DEFAULT 'telegram'"),
                  ("wa_id", "TEXT"),
                  ("household_id", "INTEGER"),
                  ("link_code", "TEXT"),
                  ("link_code_exp", "TEXT"),
                  ("cal_token", "TEXT")],
        "accounts": [("preferred_fx_rate", "TEXT"), ("closing_day", "INTEGER"), ("due_day", "INTEGER")],
        "recordatorios": [("recurrence", "TEXT"), ("list_id", "INTEGER"), ("event_id", "INTEGER")],
        "transactions": [("is_shared", "INTEGER DEFAULT 0")],
        "eventos": [("kind", "TEXT")],
        "notas": [("description", "TEXT")],
        "shopping_items": [("list_id", "INTEGER"), ("qty", "REAL"), ("unit", "TEXT"),
                           ("note", "TEXT"), ("category", "TEXT"), ("priority", "TEXT"),
                           ("position", "INTEGER"), ("added_by", "INTEGER"), ("price_est", "REAL")],
    }
    for _tbl, _newcols in _ALTERS.items():
        _existing = [r[1] for r in conn.execute(f"PRAGMA table_info({_tbl})").fetchall()]
        if not _existing:
            continue  # tabla aún no creada → la salteamos (idempotente)
        for _col, _decl in _newcols:
            if _col not in _existing:
                conn.execute(f"ALTER TABLE {_tbl} ADD COLUMN {_col} {_decl}")
    # La pareja (usuarios whitelisteados) = plan ilimitado. Idempotente: solo toca a
    # los que están en ALLOWED_USER_IDS, nunca a un usuario free que se registre después.
    if ALLOWED_USER_IDS:
        _ph = ",".join("?" for _ in ALLOWED_USER_IDS)
        conn.execute(
            f"UPDATE users SET plan='pareja' WHERE plan='free' AND telegram_id IN ({_ph})",
            ALLOWED_USER_IDS)
    # referral_code para todos los usuarios que no tengan (idempotente)
    if "referral_code" in [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]:
        _existing_codes = set(r[0] for r in conn.execute(
            "SELECT referral_code FROM users WHERE referral_code IS NOT NULL AND referral_code<>''").fetchall())
        for (_uid,) in conn.execute(
                "SELECT id FROM users WHERE referral_code IS NULL OR referral_code=''").fetchall():
            _code = gen_referral_code()
            while _code in _existing_codes:
                _code = gen_referral_code()
            _existing_codes.add(_code)
            conn.execute("UPDATE users SET referral_code=? WHERE id=?", (_code, _uid))
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_refcode ON users(referral_code)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_cal_token ON users(cal_token)")
    # Aislamiento por hogar (multi-inquilino). La pareja (ALLOWED_USER_IDS) comparte el hogar 1;
    # cualquier otro usuario = su propio hogar (household_id = su id). Idempotente.
    if "household_id" in [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]:
        if ALLOWED_USER_IDS:
            _ph = ",".join("?" for _ in ALLOWED_USER_IDS)
            conn.execute(f"UPDATE users SET household_id=1 WHERE household_id IS NULL AND telegram_id IN ({_ph})",
                         ALLOWED_USER_IDS)
        conn.execute("UPDATE users SET household_id=id WHERE household_id IS NULL")  # resto → hogar propio
        # Listas existentes (globales, sin dueño) → hogar de la pareja (Emir, id 1).
        conn.execute("UPDATE lists SET owner_user_id=1 WHERE owner_user_id IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_items_list ON shopping_items(list_id, done)")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        log.exception("no pude activar WAL (no critico)")
    # lista por defecto + asignar items sin lista (migracion idempotente)
    if not conn.execute("SELECT 1 FROM lists WHERE name='Súper' LIMIT 1").fetchone():
        conn.execute("INSERT INTO lists (name, kind, icon, shared) VALUES ('Súper','supermercado','🛒',1)")
    _deflist = conn.execute("SELECT id FROM lists WHERE name='Súper' LIMIT 1").fetchone()
    if _deflist:
        conn.execute("UPDATE shopping_items SET list_id=? WHERE list_id IS NULL", (_deflist[0],))
    # Categorías por hogar (A-3): quitar el UNIQUE global de `name` y agregar household_id.
    # Las categorías existentes (defaults) quedan COMPARTIDAS (household_id NULL). Idempotente:
    # solo reconstruye si falta household_id o el índice (name,household_id).
    _cat_cols = [r[1] for r in conn.execute("PRAGMA table_info(categories)").fetchall()]
    _has_cat_idx = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_cat_hh_name'").fetchone()
    if _cat_cols and (("household_id" not in _cat_cols) or not _has_cat_idx):
        _hh_sel = "household_id" if "household_id" in _cat_cols else "NULL"
        conn.execute("""CREATE TABLE IF NOT EXISTS categories_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'gasto',
            color TEXT, icon TEXT, active INTEGER NOT NULL DEFAULT 1,
            household_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')))""")
        conn.execute(f"""INSERT INTO categories_new (id,name,type,color,icon,active,household_id,created_at)
            SELECT id,name,type,color,icon,active,{_hh_sel},created_at FROM categories""")
        conn.execute("DROP TABLE categories")
        conn.execute("ALTER TABLE categories_new RENAME TO categories")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cat_hh_name ON categories(household_id, name)")
    if conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        conn.executemany("INSERT INTO categories (name,type,color,icon) VALUES (?,?,?,?)", [
            ("Comida","gasto","#84cc16","🛒"),
            ("Comida afuera","gasto","#f59e0b","🍽️"),
            ("Transporte","gasto","#3b82f6","🚗"),
            ("Servicios","gasto","#06b6d4","💡"),
            ("Suscripciones","gasto","#a855f7","📺"),
            ("Salud","gasto","#ef4444","💊"),
            ("Ocio","gasto","#ec4899","🎮"),
            ("Ropa","gasto","#f97316","👕"),
            ("Hogar","gasto","#10b981","🏠"),
            ("Trabajo","gasto","#6366f1","💼"),
            ("Educación","gasto","#0ea5e9","📚"),
            ("Pago de tarjeta","gasto","#94a3b8","💳"),
            ("Préstamos","gasto","#f43f5e","💸"),
            ("Otros","gasto","#94a3b8","📦"),
            ("Sueldo","ingreso","#10b981","💰"),
            ("Inversiones","ingreso","#84cc16","📈"),
            ("Otros ingresos","ingreso","#22c55e","💵"),
        ])
    conn.commit(); conn.close()


def get_user_by_tg(tg_id):
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE telegram_id=? AND active=1", (tg_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_wa(wa_id):
    if not wa_id: return None
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE wa_id=? AND active=1", (str(wa_id),)).fetchone()
    conn.close()
    return dict(row) if row else None


def household_member_ids(uid):
    """IDs de usuarios del MISMO hogar que uid (incl. uid). Aislamiento multi-inquilino:
    la pareja comparte hogar 1; cada usuario nuevo está solo en su hogar (= su id)."""
    if uid is None:
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM users WHERE COALESCE(household_id,id)=(SELECT COALESCE(household_id,id) FROM users WHERE id=?)",
            (uid,)).fetchall()]
    except Exception:
        ids = []
    finally:
        conn.close()
    return ids or [uid]


# ─── Referidos / onboarding (channel-agnostic) ──────────────────────────────
INVITE_MODE = (os.environ.get("INVITE_MODE", "admins").strip().lower() or "admins")
_REF_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # sin caracteres ambiguos (l/o/0/1/i)

def gen_referral_code(n=7):
    return "".join(secrets.choice(_REF_ALPHABET) for _ in range(n))

def get_user_by_referral_code(code):
    if not code: return None
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE referral_code=? AND active=1", (code.strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def can_invite(user):
    """Beta: solo admins (telegram_id en ALLOWED_USER_IDS) invitan. INVITE_MODE=all abre a todos."""
    if INVITE_MODE == "all": return True
    return bool(user) and user.get("telegram_id") in ALLOWED_USER_IDS

def _unique_username(conn, base):
    base = re.sub(r"[^a-z0-9]", "", (base or "").lower()) or "user"
    base = base[:20]
    cand = base; i = 1
    while conn.execute("SELECT 1 FROM users WHERE username=?", (cand,)).fetchone():
        i += 1; cand = f"{base}{i}"
    return cand

def onboard_user(channel, channel_user_id, display_name, referred_by_id=None, household_id=None):
    """Crea (o devuelve, si ya existe) un usuario. Devuelve (user_dict, temp_password|None). Idempotente.
    WhatsApp: se guarda con telegram_id = -<telefono> (negativo, sin colisión con IDs reales) + wa_id.
    Si household_id viene dado, el usuario SE UNE a ese hogar (familia); si no, hogar propio (aislado)."""
    if channel == "telegram":
        existing = get_user_by_tg(channel_user_id)
        if existing:
            return existing, None
        tg_id, wa_id = channel_user_id, None
    elif channel == "whatsapp":
        existing = get_user_by_wa(channel_user_id)
        if existing:
            return existing, None
        tg_id, wa_id = -int(channel_user_id), str(channel_user_id)
    else:
        tg_id, wa_id = None, None
    name = (display_name or "Usuario").strip()[:40] or "Usuario"
    temp_pw = secrets.token_urlsafe(6)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    try:
        username = _unique_username(conn, name)
        code = gen_referral_code()
        while conn.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone():
            code = gen_referral_code()
        conn.execute(
            "INSERT INTO users(telegram_id, name, username, password_hash, plan, "
            "referral_code, referred_by, channel, wa_id, active) VALUES (?,?,?,?,?,?,?,?,?,1)",
            (tg_id, name, username, hash_password(temp_pw), "free", code, referred_by_id, channel, wa_id))
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # Se une al hogar dado (familia) o, si no, hogar propio (aislado).
        hh = household_id if household_id else new_id
        conn.execute("UPDATE users SET household_id=? WHERE id=?", (hh, new_id))
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id=?", (new_id,)).fetchone()
        return dict(row), temp_pw
    finally:
        conn.close()


def link_whatsapp(code, phone):
    """Vincula el WhatsApp <phone> a la cuenta que generó <code> con /vincular.
    Si ya existía una cuenta WhatsApp-only con ese phone (duplicado del onboarding), la borra.
    Devuelve (ok: bool, name: str|None). Idempotente / seguro (código expira y es de un solo uso)."""
    if not code or not phone:
        return False, None
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE link_code=? AND active=1 "
            "AND (link_code_exp IS NULL OR link_code_exp >= datetime('now'))", (code.strip().upper(),)).fetchone()
        if not row:
            return False, None
        target = dict(row)
        dup = conn.execute("SELECT id FROM users WHERE wa_id=? AND id<>?", (str(phone), target["id"])).fetchone()
        if dup:  # cuenta WhatsApp duplicada (nueva/vacía) → la fusionamos borrándola
            conn.execute("DELETE FROM users WHERE id=?", (dup[0],))
        conn.execute("UPDATE users SET wa_id=?, link_code=NULL, link_code_exp=NULL WHERE id=?",
                     (str(phone), target["id"]))
        conn.commit()
        return True, target["name"]
    except Exception:
        log.exception("link_whatsapp fallo")
        return False, None
    finally:
        conn.close()

def link_telegram_via_code(code, telegram_id):
    """Vincula una cuenta de WhatsApp (que generó link_code) con un telegram_id real.
    Para el deep-link t.me/<bot>?start=link_<code> que abre el usuario de WhatsApp en Telegram.
    Devuelve (ok, name, reason). reason: None | 'invalid' | 'already_telegram'."""
    if not code or telegram_id is None:
        return False, None, "invalid"
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    try:
        wa = conn.execute(
            "SELECT * FROM users WHERE link_code=? AND active=1 "
            "AND (link_code_exp IS NULL OR link_code_exp >= datetime('now'))", (code.strip().upper(),)).fetchone()
        if not wa:
            return False, None, "invalid"
        existing = conn.execute("SELECT * FROM users WHERE telegram_id=? AND active=1", (telegram_id,)).fetchone()
        if existing and existing["id"] != wa["id"]:
            # El que abre ya tiene cuenta de Telegram propia → que use /vincular desde ahí (evita merge riesgoso).
            return False, existing["name"], "already_telegram"
        conn.execute("UPDATE users SET telegram_id=?, link_code=NULL, link_code_exp=NULL WHERE id=?",
                     (telegram_id, wa["id"]))
        conn.commit()
        return True, wa["name"], None
    except Exception:
        log.exception("link_telegram_via_code fallo")
        return False, None, "invalid"
    finally:
        conn.close()

def get_user_by_id(uid):
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_name(name):
    if not name: return None
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM users WHERE active=1").fetchall()]
    conn.close()
    n = _norm_name(name)
    for r in rows:
        if _norm_name(r['name']) == n or _norm_name(r['username']) == n: return r
    for r in rows:
        if n in _norm_name(r['name']) or n in _norm_name(r['username']): return r
    return None

def list_users():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM users WHERE active=1 ORDER BY id").fetchall()]
    conn.close()
    return rows

def current_user_id(update):
    u = get_user_by_tg(update.effective_user.id)
    return u["id"] if u else None

def current_user(update):
    return get_user_by_tg(update.effective_user.id)


def save_raw(user_id, username, kind, content):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO raw_messages (tg_user_id,tg_username,kind,content) VALUES (?,?,?,?)",
                       (user_id, username, kind, content))
    conn.commit(); raw_id = cur.lastrowid; conn.close()
    return raw_id

ACCOUNT_ALIASES = {
    "mp": "Mercado Pago", "mpago": "Mercado Pago", "mercadopago": "Mercado Pago",
    "santander": "Tarjeta Santander", "santa": "Tarjeta Santander", "santi": "Tarjeta Santander",
    "naranja": "Tarjeta Naranja", "naranjax": "Tarjeta Naranja",
    "tk": "Takenos", "cencopay": "Cenco",
    "cash": "Efectivo", "plata": "Efectivo", "efvo": "Efectivo",
}

def _norm_name(s):
    s = unicodedata.normalize("NFD", str(s or "").lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def _fuzzy_pick(name, rows):
    n = _norm_name(name)
    if not n: return None
    by_norm = {_norm_name(r["name"]): r for r in rows}
    if n in by_norm: return by_norm[n]
    subs = [r for k, r in by_norm.items() if n in k or k in n]
    if len(subs) == 1: return subs[0]
    word_idx = {}
    for k, r in by_norm.items():
        for w in k.split():
            if len(w) >= 4:
                word_idx.setdefault(w, set()).add(id(r)); word_idx[w + "_row"] = r
    words = {w: word_idx[w + "_row"] for w in list(word_idx) if not w.endswith("_row")
             and isinstance(word_idx[w], set) and len(word_idx[w]) == 1}
    if n in words: return words[n]
    candidates = list(by_norm.keys()) + list(words.keys())
    close = difflib.get_close_matches(n, candidates, n=1, cutoff=0.75)
    if close:
        k = close[0]
        return by_norm.get(k) or words.get(k)
    return None

def get_account_by_name(name, user_id=None):
    if not name: return None
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    if user_id is not None:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM accounts WHERE active=1 AND user_id=?", (user_id,)).fetchall()]
    else:
        rows = [dict(r) for r in conn.execute("SELECT * FROM accounts WHERE active=1").fetchall()]
    conn.close()
    alias = ACCOUNT_ALIASES.get(_norm_name(name))
    if alias:
        for r in rows:
            if r["name"] == alias: return r
    return _fuzzy_pick(name, rows)

def get_category_by_name(name):
    if not name: return None
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM categories WHERE active=1").fetchall()]
    conn.close()
    return _fuzzy_pick(name, rows)

def list_accounts(user_id=None):
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    if user_id is not None:
        rows = conn.execute("SELECT * FROM accounts WHERE active=1 AND user_id=? ORDER BY name", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM accounts WHERE active=1 ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_categories():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM categories WHERE active=1 ORDER BY type, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_account(user_id, name, type_="efectivo", icon=None, color=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO accounts (name,type,color,icon,user_id) VALUES (?,?,?,?,?)",
        (name, type_, color, icon, user_id))
    conn.commit(); aid = cur.lastrowid; conn.close()
    return aid

def save_transaction(tx, raw_id, user_id, recurring_id=None):
    acc = get_account_by_name(tx["account"], user_id=user_id)
    if not acc: raise ValueError(f"Cuenta no encontrada: {tx['account']}")
    cat = get_category_by_name(tx.get("category"))
    if not cat:
        try:
            learned_id = learned_category_for(user_id, tx.get("description"))
        except Exception:
            log.exception("learned_category_for fallo (no critico)")
            learned_id = None
        if learned_id:
            with db() as _c:
                _r = _c.execute("SELECT * FROM categories WHERE id=? AND active=1", (learned_id,)).fetchone()
            if _r:
                cat = dict(_r)
    occurred_at = tx.get("occurred_at") or now_local().strftime("%Y-%m-%dT%H:%M")
    if "T" not in occurred_at: occurred_at += "T" + now_local().strftime("%H:%M")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,recurring_id,raw_message_id,user_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (tx.get("type","gasto"), tx["amount"], tx.get("currency","ARS"), acc["id"],
         cat["id"] if cat else None, tx.get("description"), occurred_at, recurring_id, raw_id, user_id))
    conn.commit(); tid = cur.lastrowid; conn.close()
    return tid

# ── Splitwise (gastos compartidos) helpers DB ──────────────────────────────
def the_other_user(me_id):
    """Devuelve el dict del OTRO usuario de la pareja (asume 2 usuarios activos).
    Si hay !=2 usuarios activos, devuelve None (la pareja no esta definida)."""
    users = list_users()  # active=1
    others = [u for u in users if u["id"] != me_id]
    if len(users) == 2 and len(others) == 1:
        return others[0]
    return None


def save_shared_expense(payer_user_id, other_user_id, amount, other_share, currency,
                        description, occurred_at, transaction_id=None, raw_id=None):
    """Inserta una fila en shared_expenses (pendiente de saldar). Devuelve su id."""
    with db() as c:
        cur = c.execute(
            "INSERT INTO shared_expenses "
            "(payer_user_id, other_user_id, amount, currency, other_share, description, "
            " occurred_at, transaction_id, raw_message_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (payer_user_id, other_user_id, float(amount), currency, float(other_share),
             description, occurred_at, transaction_id, raw_id))
        return cur.lastrowid


def unsettled_shared(me_id, other_id):
    """Filas sin saldar entre la pareja (dicts), mas recientes primero."""
    with db() as c:
        rows = c.execute(
            "SELECT * FROM shared_expenses "
            "WHERE settled_at IS NULL "
            "  AND ((payer_user_id=? AND other_user_id=?) OR (payer_user_id=? AND other_user_id=?)) "
            "ORDER BY occurred_at DESC",
            (me_id, other_id, other_id, me_id)).fetchall()
    return [dict(r) for r in rows]


def settle_all_shared(me_id, other_id):
    """Marca settled_at=now() todos los splits no saldados de la pareja.
    Devuelve cuantas filas se actualizaron."""
    ts = now_local().strftime("%Y-%m-%dT%H:%M")
    with db() as c:
        cur = c.execute(
            "UPDATE shared_expenses SET settled_at=? "
            "WHERE settled_at IS NULL "
            "  AND ((payer_user_id=? AND other_user_id=?) OR (payer_user_id=? AND other_user_id=?))",
            (ts, me_id, other_id, other_id, me_id))
        return cur.rowcount


def balance_text_for(me):
    """me: dict del usuario actual. Devuelve (texto, other_dict|None)."""
    other = the_other_user(me["id"])
    if not other:
        return ("Necesito 2 usuarios activos para llevar la cuenta compartida.", None)
    rows = unsettled_shared(me["id"], other["id"])
    bal = splits.net_balance(rows, me["id"], other["id"])
    text = "\U0001F465 Balance con " + other["name"] + "\n" + \
           splits.format_balance(bal, me["name"], other["name"])
    # total USD-equivalente si hay mas de una moneda (no mezclamos ARS+USD en una sola cifra)
    if len(bal) > 1:
        total_usd = 0.0
        for cur, neto in bal.items():
            try:
                total_usd += convert_fx(neto, cur, "USD")
            except Exception:
                log.exception("convert_fx en balance %s", cur)
                total_usd = None
                break
        if total_usd is not None:
            sign = "te debe" if total_usd >= 0 else "le debes (neto)"
            text += f"\n≈ USD-equivalente: {sign} US${abs(total_usd):,.2f}"
    return (text, other)


# ── Inteligencia financiera helpers DB (Fase 2) ────────────────────────────
def category_history_amounts(user_id, category_id, exclude_tx_id=None, months=6):
    """Montos (en ARS) de gastos previos del usuario en esa categoria, ultimos N meses.
    Convierte cada monto a ARS con convert_fx para no mezclar monedas."""
    if not category_id:
        return []
    since = (now_local().replace(day=1) - timedelta(days=31 * months)).strftime("%Y-%m-01")
    with db() as c:
        rows = c.execute(
            "SELECT id, amount, currency FROM transactions "
            "WHERE user_id=? AND category_id=? AND type='gasto' AND occurred_at>=? ",
            (user_id, category_id, since)).fetchall()
    out = []
    for r in rows:
        if exclude_tx_id is not None and r["id"] == exclude_tx_id:
            continue
        try:
            out.append(convert_fx(r["amount"], r["currency"], "ARS"))
        except Exception:
            if r["currency"] == "ARS":
                out.append(float(r["amount"]))
    return out


def budgets_for_user(user_id):
    """[{category_id, cat_name, limit, spent_ars}] del mes en curso.
    spent_ars suma TODOS los gastos de la categoria convertidos a ARS."""
    mes_ini = now_local().strftime("%Y-%m-01")
    with db() as c:
        try:
            bud = c.execute(
                "SELECT b.category_id, b.amount AS lim, cat.name AS cat_name "
                "FROM budgets b JOIN categories cat ON cat.id=b.category_id "
                "WHERE b.user_id=?", (user_id,)).fetchall()
        except Exception:
            log.exception("budgets_for_user: tabla budgets no disponible")
            return []
        out = []
        for b in bud:
            txs = c.execute(
                "SELECT amount, currency FROM transactions "
                "WHERE type='gasto' AND category_id=? AND user_id=? AND occurred_at>=?",
                (b["category_id"], user_id, mes_ini)).fetchall()
            spent = 0.0
            for t in txs:
                try:
                    spent += convert_fx(t["amount"], t["currency"], "ARS")
                except Exception:
                    if t["currency"] == "ARS":
                        spent += float(t["amount"])
            out.append({"category_id": b["category_id"], "cat_name": b["cat_name"],
                        "limit": float(b["lim"]), "spent_ars": round(spent, 2)})
        return out


def upsert_category_learning(user_id, description, category_id):
    """Por cada keyword de la descripcion, incrementa el count de (keyword->category_id)."""
    if not category_id:
        return
    kws = finance.learn_keywords(description)
    if not kws:
        return
    with db() as c:
        for kw in kws:
            c.execute(
                "INSERT INTO category_learning (user_id, keyword, category_id, count) "
                "VALUES (?,?,?,1) "
                "ON CONFLICT(user_id, keyword, category_id) DO UPDATE SET count=count+1",
                (user_id, kw, category_id))


def learned_category_for(user_id, description):
    """category_id mas aprendido para las keywords de la descripcion, o None."""
    kws = finance.learn_keywords(description)
    if not kws:
        return None
    placeholders = ",".join(["?"] * len(kws))
    with db() as c:
        rows = c.execute(
            f"SELECT category_id, SUM(count) AS count FROM category_learning "
            f"WHERE user_id=? AND keyword IN ({placeholders}) GROUP BY category_id",
            [user_id] + kws).fetchall()
    return finance.pick_learned_category([dict(r) for r in rows])


def recurring_candidates(user_id, months_back=4):
    """Candidatos a recurrente del usuario en los ultimos months_back meses."""
    since = (now_local().replace(day=1) - timedelta(days=31 * months_back)).strftime("%Y-%m-01")
    with db() as c:
        txs = [dict(r) for r in c.execute(
            "SELECT amount, currency, description, occurred_at FROM transactions "
            "WHERE user_id=? AND type='gasto' AND occurred_at>=?",
            (user_id, since)).fetchall()]
        rec = c.execute(
            "SELECT description FROM recurring WHERE user_id=? AND active=1", (user_id,)).fetchall()
    existing = {finance._norm_desc(r["description"]) for r in rec}
    return finance.detect_recurring(txs, existing_keys=existing)


def create_savings_goal(user_id, name, target_amount, currency="USD", deadline=None):
    with db() as c:
        cur = c.execute(
            "INSERT INTO savings_goals (user_id, name, target_amount, currency, deadline) "
            "VALUES (?,?,?,?,?)", (user_id, name, float(target_amount), currency, deadline))
        return cur.lastrowid


def add_to_savings_goal(user_id, name, add_amount):
    """Suma add_amount a la meta cuyo nombre matchea (case-insensitive). Devuelve la fila o None."""
    with db() as c:
        row = c.execute(
            "SELECT * FROM savings_goals WHERE user_id=? AND active=1 AND LOWER(name)=LOWER(?)",
            (user_id, name)).fetchone()
        if not row:
            return None
        c.execute("UPDATE savings_goals SET current_amount=current_amount+? WHERE id=?",
                  (float(add_amount), row["id"]))
        row2 = c.execute("SELECT * FROM savings_goals WHERE id=?", (row["id"],)).fetchone()
        return dict(row2)


def list_savings_goals(user_id):
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM savings_goals WHERE user_id=? AND active=1 ORDER BY created_at DESC",
            (user_id,)).fetchall()]


def _months_until(deadline_str):
    """Meses (>=0) desde hoy hasta deadline (YYYY-MM-DD). None/pasado -> 0."""
    if not deadline_str:
        return 0
    try:
        d = datetime.fromisoformat(deadline_str[:10]).date()
    except Exception:
        return 0
    today = now_local().date()
    if d <= today:
        return 0
    return (d.year - today.year) * 12 + (d.month - today.month)


def _days_in_month(dt):
    import calendar as _cal
    return _cal.monthrange(dt.year, dt.month)[1]


def _first_account_name(user_id):
    accs = list_accounts(user_id=user_id)
    return accs[0]["name"] if accs else "Efectivo"


# ── Lista de compras helpers DB (Fase 6) ───────────────────────────────────
def _default_list_id(uid):
    members = household_member_ids(uid)
    ph = ",".join("?" for _ in members)
    with db() as c:
        r = c.execute(f"SELECT id FROM lists WHERE name='Súper' AND owner_user_id IN ({ph}) LIMIT 1", members).fetchone()
        if r:
            return r["id"]
        r = c.execute(f"SELECT id FROM lists WHERE COALESCE(is_template,0)=0 AND owner_user_id IN ({ph}) ORDER BY id LIMIT 1", members).fetchone()
        return r["id"] if r else None


# Pistas de icono/tipo segun el nombre de una lista nueva (mejor esfuerzo, cosmetico).
_LIST_HINTS = [
    (("farmacia", "remedio", "medic"), "💊", "farmacia"),
    (("regalo", "navidad", "cumple"), "🎁", "regalos"),
    (("ferreteria", "ferret", "obra", "pintura"), "🔧", "ferreteria"),
    (("verduleria", "verdura", "fruta"), "🥬", "verduleria"),
    (("super", "compras", "mercado", "almacen"), "🛒", "supermercado"),
    (("vacaciones", "viaje", "valija"), "🧳", "viaje"),
    (("libreria", "utiles", "escuela", "colegio"), "✏️", "libreria"),
    (("cumpleaños", "fiesta", "asado", "picada"), "🎉", "evento"),
]


def _guess_list_meta(name_norm):
    for kws, icon, kind in _LIST_HINTS:
        for kw in kws:
            if kw in name_norm:
                return icon, kind
    return "📝", "generica"


_LIST_COLS = "id,name,icon,kind,target_date,recurrence"


def _resolve_list(name, uid, create=True):
    """Devuelve {id,name,icon,kind,target_date,recurrence} de la lista por nombre
    (insensible a acentos/mayus). name vacio -> lista por defecto (Súper) DEL HOGAR de uid.
    Si no existe y create=True, la crea. Excluye plantillas. Scopeado por hogar (aislamiento)."""
    members = household_member_ids(uid)
    ph = ",".join("?" for _ in members)
    if not name or not name.strip():
        lid = _default_list_id(uid)
        if lid is None:
            if not create:
                return None
            with db() as c:  # crear la lista por defecto del hogar
                c.execute("INSERT INTO lists (name, kind, icon, owner_user_id, shared) "
                          "VALUES ('Súper','supermercado','🛒',?,1)", (uid,))
                lid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        with db() as c:
            r = c.execute(f"SELECT {_LIST_COLS} FROM lists WHERE id=?", (lid,)).fetchone()
        return dict(r) if r else None
    q = _norm_name(name)
    with db() as c:
        rows = c.execute(f"SELECT {_LIST_COLS} FROM lists WHERE COALESCE(is_template,0)=0 AND owner_user_id IN ({ph})", members).fetchall()
        for r in rows:
            if _norm_name(r["name"]) == q:
                return dict(r)
        if not create:
            return None
        icon, kind = _guess_list_meta(q)
        clean = name.strip().title()
        c.execute("INSERT INTO lists (name, kind, icon, owner_user_id, shared) VALUES (?,?,?,?,1)",
                  (clean, kind, icon, uid))
        rid = c.execute("SELECT last_insert_rowid() AS id").fetchone()[0]
    return {"id": rid, "name": clean, "icon": icon, "kind": kind,
            "target_date": None, "recurrence": None}


def _find_template(name, uid):
    """Busca una plantilla (is_template=1) por nombre DENTRO DEL HOGAR de uid. dict o None."""
    if not name or not name.strip():
        return None
    members = household_member_ids(uid)
    ph = ",".join("?" for _ in members)
    q = _norm_name(name)
    with db() as c:
        rows = c.execute(f"SELECT {_LIST_COLS} FROM lists WHERE COALESCE(is_template,0)=1 AND owner_user_id IN ({ph})", members).fetchall()
    for r in rows:
        if _norm_name(r["name"]) == q:
            return dict(r)
    return None


def _list_subtitle(lst):
    """Linea de fecha/recurrencia para el encabezado de una lista, o None."""
    if not lst:
        return None
    parts = []
    if lst.get("target_date"):
        try:
            parts.append("📅 " + fmt_d(lst["target_date"]))
        except Exception:
            parts.append("📅 " + str(lst["target_date"]))
    rec = lst.get("recurrence")
    if rec:
        parts.append({"daily": "🔁 diaria", "weekly": "🔁 semanal",
                      "monthly": "🔁 mensual"}.get(rec, "🔁 " + str(rec)))
    return " · ".join(parts) if parts else None


def _shopping_items(list_id=None, uid=None):
    if list_id is None:
        list_id = _default_list_id(uid)
    if list_id is None:
        return []
    with db() as c:
        rows = c.execute(
            "SELECT id, text, done, qty, unit, category, position FROM shopping_items "
            "WHERE list_id=? ORDER BY done ASC, COALESCE(position, id) ASC, id ASC",
            (list_id,)).fetchall()
    return [dict(r) for r in rows]


def _render_shopping(list_id, lst=None):
    """(texto, InlineKeyboardMarkup|None) de una lista: botones ▫️ para tildar c/item."""
    if lst is None:
        with db() as c:
            r = c.execute(f"SELECT {_LIST_COLS} FROM lists WHERE id=?", (list_id,)).fetchone()
        lst = dict(r) if r else {"name": "Lista", "icon": "🛒"}
    items = _shopping_items(list_id)
    text = shopping.render_list(items, lst.get("name"), lst.get("icon"), subtitle=_list_subtitle(lst))
    pend = [i for i in items if not i.get("done")]
    done_n = len(items) - len(pend)
    rows = []
    for it in pend[:40]:
        label = "▫️ " + shopping._fmt_qty(it)
        if len(label) > 45:
            label = label[:44] + "…"
        rows.append([InlineKeyboardButton(label, callback_data=f"lscheck:{it['id']}")])
    if done_n:
        rows.append([InlineKeyboardButton(f"🧹 Limpiar {done_n} comprado(s)",
                                          callback_data=f"lsclear:{list_id}")])
    return text, (InlineKeyboardMarkup(rows) if rows else None)


def save_recurring(r, raw_id, user_id, fire_immediately=True):
    import calendar as _cal
    acc = get_account_by_name(r["account"], user_id=user_id)
    if not acc: raise ValueError(f"Cuenta no encontrada: {r['account']}")
    cat = get_category_by_name(r.get("category"))
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO recurring (type,amount,currency,account_id,category_id,description,frequency,day_of_month,next_occurrence,total_installments,raw_message_id,user_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (r.get("type","gasto"), r["amount"], r.get("currency","ARS"), acc["id"],
         cat["id"] if cat else None, r["description"], r.get("frequency","monthly"),
         r.get("day_of_month"), r["next_occurrence"], r.get("total_installments"), raw_id, user_id))
    rid = cur.lastrowid
    fired_tx_id = None
    if fire_immediately:
        total = r.get("total_installments")
        cuota_str = f" (cuota 1/{total})" if total else ""
        desc_full = r["description"] + cuota_str
        # Para tarjetas de credito con cierre Y vencimiento, la cuota se cobra en el
        # VENCIMIENTO del cierre donde postea hoy (no el cierre). Si falta el vencimiento,
        # caemos al cierre como antes.
        _occ_now = now_local()
        _cd = acc.get("closing_day") if acc.get("type") == "credito" else None
        _dd = acc.get("due_day") if acc.get("type") == "credito" else None
        if total and _cd and _dd:
            _venc = vencimientos.venc_de_cuota(_cd, _dd, _occ_now.date())
            occurred_at = _venc.strftime("%Y-%m-%dT09:00")
        elif total and _cd:
            _close = vencimientos.proxima_fecha_para_cuota(_cd, _occ_now.date())
            occurred_at = _close.strftime("%Y-%m-%dT09:00")
        else:
            occurred_at = _occ_now.strftime("%Y-%m-%dT%H:%M")
        cur2 = conn.execute(
            "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,recurring_id,user_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (r.get("type","gasto"), r["amount"], r.get("currency","ARS"), acc["id"],
             cat["id"] if cat else None, desc_full, occurred_at, rid, user_id))
        fired_tx_id = cur2.lastrowid
        if total and 1 >= total:
            conn.execute("UPDATE recurring SET active=0, installments_fired=1 WHERE id=?", (rid,))
        else:
            if total and _cd and _dd:
                # próxima cuota = vencimiento del mes siguiente; fijamos day_of_month=vencimiento
                new_next = recurrence.next_occurrence(r.get("frequency","monthly"), occurred_at[:10], _dd)
                conn.execute("UPDATE recurring SET next_occurrence=?, day_of_month=?, installments_fired=1 WHERE id=?",
                             (new_next, _dd, rid))
            else:
                base = now_local().date().strftime("%Y-%m-%d")
                new_next = recurrence.next_occurrence(r.get("frequency", "monthly"), base, r.get("day_of_month"))
                conn.execute("UPDATE recurring SET next_occurrence=?, installments_fired=1 WHERE id=?", (new_next, rid))
    conn.commit(); conn.close()
    return rid, fired_tx_id

def save_evento(e, raw_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO eventos (title,starts_at,location,notes,kind,raw_message_id,user_id) VALUES (?,?,?,?,?,?,?)",
        (e["title"], e["starts_at"], e.get("location"), e.get("notes"), e.get("kind"), raw_id, user_id))
    conn.commit(); eid = cur.lastrowid; conn.close()
    return eid

def save_recordatorio(text, remind_at, user_id, source=None, raw_id=None, event_id=None, list_id=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO recordatorios (text,remind_at,source,raw_message_id,user_id,event_id,list_id) VALUES (?,?,?,?,?,?,?)",
                       (text, remind_at, source, raw_id, user_id, event_id, list_id))
    conn.commit(); rid = cur.lastrowid; conn.close()
    return rid

def save_tarea(t, raw_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO tareas (text,priority,due_at,raw_message_id,user_id) VALUES (?,?,?,?,?)",
                       (t["text"], t.get("priority","media"), t.get("due_at"), raw_id, user_id))
    conn.commit(); tid = cur.lastrowid; conn.close()
    return tid

def save_habito(h, raw_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO habito_logs (name,value,unit,note,raw_message_id,user_id) VALUES (?,?,?,?,?,?)",
                       (h["name"].lower(), h.get("value"), h.get("unit"), h.get("note"), raw_id, user_id))
    conn.commit(); hid = cur.lastrowid; conn.close()
    return hid

def save_nota(n, raw_id, user_id):
    tags = json.dumps(n.get("tags") or [], ensure_ascii=False)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO notas (text,tags,description,raw_message_id,user_id) VALUES (?,?,?,?,?)",
                       (n["text"], tags, n.get("description"), raw_id, user_id))
    conn.commit(); nid = cur.lastrowid; conn.close()
    return nid

def compute_next_monthly(current_iso, day_of_month):
    cur = datetime.fromisoformat(current_iso).date()
    ny, nm = (cur.year+1, 1) if cur.month == 12 else (cur.year, cur.month+1)
    last = calendar.monthrange(ny, nm)[1]
    d = min(day_of_month or cur.day, last)
    return f"{ny}-{nm:02d}-{d:02d}"

def is_allowed(update):
    """Permitido = usuario registrado activo (existe en users por telegram_id).
    La beta es solo-invitación: se entra vía deep-link de referido (ver start_cmd)."""
    try:
        return get_user_by_tg(update.effective_user.id) is not None
    except Exception:
        return False

REGISTER_MSG = ("👋 Yumi todavía es por invitación.\n"
                "Pedile a quien te invitó su link de Yumi para entrar. "
                "Pronto vas a poder registrarte solo.")

async def send_register_prompt(update):
    try:
        await update.message.reply_text(REGISTER_MSG)
    except Exception:
        log.exception("no pude mandar register prompt")

def _strip_json(content):
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"): content = content[4:]
        content = content.strip()
    return content


def build_filter(filters, user_id=None):
    where = []
    params = []
    f = filters or {}
    if user_id is not None:
        where.append("t.user_id = ?"); params.append(user_id)
    if f.get('ids'):
        placeholders = ','.join(['?'] * len(f['ids']))
        where.append(f"t.id IN ({placeholders})")
        params.extend([int(x) for x in f['ids']])
    if f.get('description_contains'):
        where.append("LOWER(COALESCE(t.description,'')) LIKE LOWER(?)")
        params.append(f"%{f['description_contains']}%")
    if f.get('current_account'):
        acc = get_account_by_name(f['current_account'], user_id=user_id)
        if acc: where.append("t.account_id = ?"); params.append(acc['id'])
    if f.get('current_category'):
        cat = get_category_by_name(f['current_category'])
        if cat: where.append("t.category_id = ?"); params.append(cat['id'])
    if f.get('type'):
        where.append("t.type = ?"); params.append(f['type'])
    if f.get('currency'):
        where.append("t.currency = ?"); params.append(f['currency'])
    if f.get('date_from'):
        where.append("t.occurred_at >= ?"); params.append(f['date_from'])
    if f.get('date_to'):
        where.append("t.occurred_at <= ?"); params.append(f['date_to'] + "T23:59")
    where_clause = " AND ".join(where) if where else "1=1"
    order_by = "t.occurred_at ASC" if f.get('order') == 'oldest' else "t.occurred_at DESC"
    limit_clause = f" LIMIT {int(f['limit'])}" if f.get('limit') else ""
    return where_clause, params, order_by, limit_clause


def query_transactions(filters, user_id=None):
    where, params, order, limit = build_filter(filters, user_id=user_id)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"SELECT t.id, t.amount, t.currency, t.description, t.type, t.occurred_at, "
        f"a.name AS acc_name FROM transactions t JOIN accounts a ON a.id=t.account_id "
        f"WHERE {where} ORDER BY {order}{limit}", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def apply_move(ids, target_account_id=None, target_category_id=None):
    if not ids: return 0
    placeholders = ','.join(['?'] * len(ids))
    set_clauses = []
    set_params = []
    if target_account_id is not None:
        set_clauses.append("account_id = ?"); set_params.append(target_account_id)
    if target_category_id is not None:
        set_clauses.append("category_id = ?"); set_params.append(target_category_id)
    if not set_clauses: return 0
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"UPDATE transactions SET {', '.join(set_clauses)} WHERE id IN ({placeholders})",
                 set_params + ids)
    conn.commit(); conn.close()
    return len(ids)


def apply_delete(ids):
    if not ids: return 0
    placeholders = ','.join(['?'] * len(ids))
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", ids)
    conn.commit(); conn.close()
    return len(ids)


def make_op_id():
    return f"op{int(datetime.now().timestamp()*1000)}{os.urandom(2).hex()}"


def preview_lines(rows, n=5):
    out = []
    for r in rows[:n]:
        sign = "-" if r['type']=='gasto' else "+"
        desc = r['description'] or '(sin desc)'
        out.append(f"#{r['id']} {sign}{r['amount']:,.2f} {r['currency']} · {desc} ({r['acc_name']})")
    return out


def get_dolar_rate(rate_type="blue"):
    now = _time.time()
    if rate_type in _rate_cache:
        ts, value = _rate_cache[rate_type]
        if now - ts < RATE_TTL: return value
    try:
        url = f"https://dolarapi.com/v1/dolares/{rate_type}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (asistente-bot)"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        rate = (data.get("compra",0) + data.get("venta",0)) / 2
        if not rate: return None
        _rate_cache[rate_type] = (now, rate)
        return rate
    except Exception:
        log.exception("Rate fetch fail"); return None


def convert_amount(amount, from_cur, to_cur, rate_type="blue", explicit_rate=None):
    if from_cur == to_cur: return amount, None
    if explicit_rate: rate = explicit_rate
    else:
        rate = get_dolar_rate(rate_type)
        if not rate: raise ValueError("No pude obtener cotización.")
    if from_cur == "ARS" and to_cur == "USD": return amount / rate, rate
    elif from_cur == "USD" and to_cur == "ARS": return amount * rate, rate
    else: raise ValueError(f"Conversión no soportada: {from_cur}->{to_cur}")


PARSER_TOOL = {
    "name": "registrar_acciones",
    "description": "Registra una o mas acciones extraidas del mensaje del usuario.",
    "input_schema": {
        "type": "object",
        "properties": {
            "acciones": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string", "enum": [
                            "transaccion","transferencia","recurrente","mover","eliminar","editar",
                            "evento","recordatorio","tarea","habito","nota","crear_cuenta","editar_cuenta","consulta",
                            "gasto_compartido","saldar","meta_ahorro","lista_compra","alerta_dolar",
                            "set_takenos_rate","dolar","afford","precio","desconocido"]},
                        "confidence": {"type": "number"},
                        "data": {"type": "object"}
                    },
                    "required": ["intent", "data"]
                }
            }
        },
        "required": ["acciones"]
    }
}

PARSER_TEMPLATE = """Sos el parser de un asistente personal en espanol rioplatense (finanzas, agenda, tareas, habitos, notas).
Tu UNICA salida es la tool `registrar_acciones` con un array `acciones`.

HOY: __TODAY__ (__DOW__) - HORA: __NOW__ - TZ: __TZ__
QUIEN ESCRIBE: __ME__ (id=__ME_ID__).
OTROS USUARIOS: __OTHERS__

CUENTAS DE __ME__ (usa el nombre EXACTO en `account`):
__ACCOUNTS__

CATEGORIAS (compartidas):
__CATEGORIES__

REGLA DE ORO: SIEMPRE UN ARRAY.
Un mensaje puede traer VARIAS acciones de tipos distintos. Detecta cada una y devolve un array.
Separadores: "y", "tambien", saltos de linea, vinetas. JAMAS sumes montos de items distintos.

TABLA DE DECISION:
1. Verbo en pasado sobre dinero (pague, gaste, compre, cobre, me pagaron) -> transaccion
2. Verbo en pasado sobre actividad personal (hice, entrene, lei, corri, medite) -> habito
3. Movimiento entre dos cuentas propias (pase/converti/mande de X a Y) -> transferencia
4. Pago repetido o en cuotas (todos los meses, N cuotas, agenda <servicio>) -> recurrente
5. recordame/avisame/acordame + momento futuro -> recordatorio. Con fecha u hora explicita es SIEMPRE recordatorio.
6. Cita con persona/lugar/hora (cena con, turno, reunion) -> evento
7. Pendiente accionable SIN momento exacto (tengo que, hay que) -> tarea
8. anota/apunta/acordate que/idea: -> nota
9. "crear cuenta X" / "agrega la cuenta X" / "nueva cuenta Y" -> crear_cuenta
9b. "renombra/edita/cambia el nombre de la cuenta X a Y" -> editar_cuenta (old_name=X, new_name=Y)
10. Pregunta sobre datos (cuanto gaste, que tengo) -> consulta
11. borra/move/edita/cambia con #IDs o filtros -> eliminar/mover/editar
12. Nada matchea -> desconocido con data.aclaracion = UNA pregunta concreta

MULTI-USUARIO:
- Por default las consultas son de __ME__. Si mencionan a otro (Lisa, ella, juntos, los dos, ambos, compartido), agregalo en `filters.scope`.
- scope valores: "mine" (default), "ours" (los dos), "user:<nombre>" (otro especifico).
- "cuanto gastamos los dos este mes" -> scope:"ours"
- "cuanto gasto Lisa" -> scope:"user:Lisa"
- "cuanto gaste yo" -> scope:"mine" o ausente
- Para REGISTRAR (transaccion, recurrente, evento, etc.) NUNCA podes registrar a nombre del otro. Si dice "Lisa pago algo" -> desconocido con aclaracion="Solo puedo registrar tus propios gastos. Pedile a Lisa que lo cargue ella."

MONTOS (Argentina):
luca=1000 -> "50 lucas"=50000 - media luca=500 - palo=1000000 -> "1,5 palos"=1500000
gamba=100 - 2k=2000 - 1.500=1500 (punto = miles) - dolares/USD/u$s/verdes -> USD - default ARS

FECHAS (resolver TODO a ISO usando HOY=__TODAY__ __DOW__):
manana=+1d - pasado manana=+2d - en una hora=__NOW__+1h
el viernes=viernes mas proximo - el viernes que viene=siguiente
fin de mes=ultimo dia del mes - recordatorio sin hora -> 09:00

CAMPOS DE `data`:
transaccion: {"type":"gasto"|"ingreso","amount":num,"currency":"ARS"|"USD"|"EUR","category":str,"account":str,"description":str,"occurred_at":"YYYY-MM-DDTHH:MM"}
transferencia: {"amount":num,"from_account":str,"to_account":str,"from_currency":str,"to_currency":str,"exchange_rate":num|null,"rate_type":"oficial"|"blue"|"mep"|"cripto"|null,"description":str,"occurred_at":"YYYY-MM-DDTHH:MM"}
recurrente: {"type":"gasto"|"ingreso","amount":num,"currency":str,"category":str,"account":str,"description":str,"frequency":"monthly"|"weekly"|"annual","day_of_month":num,"next_occurrence":"YYYY-MM-DD","total_installments":num|null}
mover: {"target_account":str|null,"target_category":str|null,"filters":{...}}
eliminar: {"filters":{...}}
editar: {"id":int,"amount":num|null,"currency":str|null,"description":str|null,"category":str|null,"account":str|null,"occurred_at":str|null}
evento: {"title":str,"starts_at":"YYYY-MM-DDTHH:MM","location":str|null,"notes":str|null,"kind":"turno"|null,"reminder_offsets":[int]|null}  (kind="turno" para turnos medicos; reminder_offsets=minutos antes para avisar, ej [60,30,10])
recordatorio: {"text":str,"remind_at":"YYYY-MM-DDTHH:MM","recurrence":"daily"|"weekly"|"monthly"|null}
tarea: {"text":str,"priority":"baja"|"media"|"alta","due_at":"YYYY-MM-DD"|null}
habito: {"name":str,"value":num|null,"unit":str|null,"note":str|null}
nota: {"text":str,"tags":[str]|null}
crear_cuenta: {"name":str,"type":"efectivo"|"billetera"|"credito"|"banco"|"inversion","icon":str|null}
editar_cuenta: {"old_name":str,"new_name":str}  (renombrar una cuenta existente)
consulta: {"type":"resumen"|"transacciones"|"recurrentes"|"cuentas"|"eventos"|"tareas"|"habitos"|"notas"|"pendientes"|"cotizacion"|"balance"|"balance_pareja"|"otro","intencion":"total"|"lista"|"promedio"|"ranking"|"max"|"min"|"conteo"|null,"filters":{"keyword":str|null,"category":str|null,"account":str|null,"type":"gasto"|"ingreso"|null,"currency":"ARS"|"USD"|"EUR"|null,"period":"hoy"|"ayer"|"semana"|"semana_pasada"|"mes"|"mes_pasado"|"ano"|"ano_pasado"|"todo"|null,"date_from":"YYYY-MM-DD"|null,"date_to":"YYYY-MM-DD"|null,"amount_min":num|null,"amount_max":num|null,"scope":"mine"|"ours"|"user:<nombre>"|null},"limit":int|null,"group_by":"category"|"account"|"user"|null,"order":"newest"|"oldest"|"largest"|null,"compare_period":"mes_pasado"|"semana_pasada"|"ano_pasado"|null}
gasto_compartido: {"amount":num,"currency":"ARS"|"USD"|"EUR","category":str,"account":str,"description":str,"other_share":num|null,"occurred_at":"YYYY-MM-DDTHH:MM"}
saldar: {}
meta_ahorro: {"name":str,"target_amount":num|null,"currency":"ARS"|"USD"|"EUR"|null,"deadline":"YYYY-MM-DD"|null,"add_amount":num|null}
lista_compra: {"action":"add"|"check"|"uncheck"|"remove"|"show"|"clear"|"bought"|"remind"|"save_template"|"use_template","list":str|null,"item":str|null,"amount":num|null,"account":str|null,"currency":"ARS"|"USD"|"EUR"|null,"remind_at":"YYYY-MM-DDTHH:MM"|null,"target_date":"YYYY-MM-DD"|null,"recurrence":"weekly"|"monthly"|"daily"|null}  (list=nombre de la lista, null=la de compras por defecto. add=agregar; check/remove=tachar; uncheck=destachar; show=mostrar; clear=vaciar; bought="compré la lista" (marca todo comprado; si dice monto va amount/account/currency para anotar el gasto); remind="recordame la lista" (remind_at=cuando); save_template=guardar la lista como plantilla (item=nombre de la plantilla); use_template=armar una lista desde una plantilla (item=nombre de la plantilla, list=lista destino). En item conservá la cantidad si la dicen, ej "2 kg de papa". target_date/recurrence = fecha objetivo / periodicidad de la lista. Para "agregá los ingredientes de <plato>" devolvé un add por cada ingrediente tipico.)
alerta_dolar: {"rate_type":"oficial"|"blue"|"mep"|"cripto"|"takenos","direction":"above"|"below","threshold":num}
set_takenos_rate: {"value":num}
dolar: {}
afford: {"afford_amount":num,"currency":"ARS"|"USD"|null,"afford_category":str|null}
desconocido: {"aclaracion":str}

ALIAS de cuentas: mp/mercadopago->Mercado Pago - santander/santi->Tarjeta Santander - naranja->Tarjeta Naranja - cenco->Cenco - tk->Takenos - cash/plata->Efectivo
Categoria: inferila (nafta/uber/sube->Transporte - super/verduleria->Comida - resto/cafe/delivery->Comida afuera - luz/gas/internet->Servicios - netflix/spotify->Suscripciones - farmacia->Salud). Sin senal -> Otros.
Gasto chico sin cuenta dicha -> account="Efectivo" si existe; si no, la primera cuenta del usuario.
confidence: 0.9+ inequivoco - 0.6-0.85 algun campo inferido - <0.5 mejor desconocido.

EJEMPLOS:
"recordame manana a las 11am pagar el internet"
-> [{"intent":"recordatorio","confidence":0.97,"data":{"text":"Pagar el internet","remind_at":"<manana>T11:00"}}]

"gaste 5 lucas en nafta y 2 en el kiosco, todo con santander"
-> 2 transacciones: {amount:5000,category:"Transporte",account:"Tarjeta Santander",description:"Nafta"} y {amount:2000,category:"Comida",account:"Tarjeta Santander",description:"Kiosco"}

"cena con Ana el viernes 21hs en Palermo y recordame comprar vino ese dia a las 18"
-> evento + recordatorio

"turno con el cardiologo el martes 10am, recordame 60, 30 y 10 minutos antes"
-> [{"intent":"evento","confidence":0.95,"data":{"title":"Turno cardiologo","starts_at":"<martes>T10:00","kind":"turno","reminder_offsets":[60,30,10]}}]

"crear cuenta MP nueva tipo billetera"
-> crear_cuenta{name:"MP",type:"billetera",icon:"💳"}

"agrega la cuenta Visa Galicia"
-> crear_cuenta{name:"Visa Galicia",type:"credito"}

"renombra la cuenta Mercopal a Mercado Pago" / "cambiale el nombre a la cuenta X por Y"
-> editar_cuenta{old_name:"Mercopal",new_name:"Mercado Pago"}

EJEMPLOS DE CONSULTA:
"cuanto llevo gastado en combustible este mes?"
-> consulta{type:"transacciones",intencion:"total",filters:{keyword:"combustible",type:"gasto",period:"mes"}}

"mostrame mis ultimas 2 transacciones"
-> consulta{type:"transacciones",intencion:"lista",limit:2,order:"newest"}

"cuanto gastamos los dos este mes?"
-> consulta{type:"transacciones",intencion:"total",filters:{type:"gasto",period:"mes",scope:"ours"}}

"cuanto gasto Lisa este mes?"
-> consulta{type:"transacciones",intencion:"total",filters:{type:"gasto",period:"mes",scope:"user:Lisa"}}

"comparativa este mes entre nosotros"
-> consulta{type:"transacciones",intencion:"ranking",filters:{type:"gasto",period:"mes",scope:"ours"},group_by:"user"}

"cuanto gaste con naranja este mes?"
-> consulta{type:"transacciones",intencion:"total",filters:{account:"Tarjeta Naranja",type:"gasto",period:"mes"}}

"en que gaste mas este mes?"
-> consulta{type:"transacciones",intencion:"ranking",filters:{type:"gasto",period:"mes"},group_by:"category"}

"cuantas veces compre en mp este mes?"
-> consulta{type:"transacciones",intencion:"conteo",filters:{account:"Mercado Pago",period:"mes"}}

"cuanto tengo en mercadopago"
-> consulta{type:"balance",filters:{account:"Mercado Pago"}}

"resumen del mes" / "como voy"
-> consulta{type:"resumen"}

"resumen compartido del mes"
-> consulta{type:"resumen",filters:{scope:"ours"}}

"el otro dia estuvo bueno lo de marcos"
-> [{"intent":"desconocido","confidence":0.3,"data":{"aclaracion":"Lo guardo como nota o era otra cosa?"}}]

EJEMPLOS FASE 1-6 (nuevos intents; SIEMPRE como array):
"pagué 80 lucas el súper, mitad de Lisa"
-> [{"intent":"gasto_compartido","confidence":0.93,"data":{"amount":80000,"currency":"ARS","category":"Comida","account":"Efectivo","description":"Super","other_share":40000}}]

"pagué 12000 el delivery con mp, lo dividimos"
-> [{"intent":"gasto_compartido","confidence":0.9,"data":{"amount":12000,"currency":"ARS","category":"Comida afuera","account":"Mercado Pago","description":"Delivery"}}]

"saldá lo que debemos" / "estamos a mano"
-> [{"intent":"saldar","confidence":0.95,"data":{}}]

"¿quién debe?" / "como vamos con los gastos compartidos"
-> [{"intent":"consulta","confidence":0.9,"data":{"type":"balance_pareja"}}]

"quiero juntar 2000 dolares para vacaciones antes de fin de ano"
-> [{"intent":"meta_ahorro","confidence":0.95,"data":{"name":"Vacaciones","target_amount":2000,"currency":"USD","deadline":"2026-12-31"}}]

"sume 100 usd a vacaciones"
-> [{"intent":"meta_ahorro","confidence":0.95,"data":{"name":"Vacaciones","add_amount":100,"currency":"USD"}}]

"agregá 2 kg de papa y leche a la lista"
-> [{"intent":"lista_compra","confidence":0.95,"data":{"action":"add","item":"2 kg de papa"}},{"intent":"lista_compra","confidence":0.95,"data":{"action":"add","item":"leche"}}]

"sumá ibuprofeno a la lista de la farmacia"
-> [{"intent":"lista_compra","confidence":0.93,"data":{"action":"add","list":"Farmacia","item":"ibuprofeno"}}]

"agregá los ingredientes para hacer milanesas con puré"
-> [{"intent":"lista_compra","confidence":0.9,"data":{"action":"add","item":"carne para milanesa"}},{"intent":"lista_compra","confidence":0.9,"data":{"action":"add","item":"pan rallado"}},{"intent":"lista_compra","confidence":0.9,"data":{"action":"add","item":"huevos"}},{"intent":"lista_compra","confidence":0.9,"data":{"action":"add","item":"papa"}},{"intent":"lista_compra","confidence":0.9,"data":{"action":"add","item":"leche"}},{"intent":"lista_compra","confidence":0.9,"data":{"action":"add","item":"manteca"}}]

"mostrame la lista de compras"
-> [{"intent":"lista_compra","confidence":0.97,"data":{"action":"show"}}]

"ya compré la leche"
-> [{"intent":"lista_compra","confidence":0.9,"data":{"action":"check","item":"leche"}}]

"vaciá la lista de compras"
-> [{"intent":"lista_compra","confidence":0.95,"data":{"action":"clear"}}]

"compré toda la lista del super, gasté 45000 con mercado pago"
-> [{"intent":"lista_compra","confidence":0.92,"data":{"action":"bought","list":"Súper","amount":45000,"currency":"ARS","account":"Mercado Pago"}}]

"ya compré todo lo de la lista"
-> [{"intent":"lista_compra","confidence":0.9,"data":{"action":"bought"}}]

"recordame comprar la lista del super mañana a las 10"
-> [{"intent":"lista_compra","confidence":0.93,"data":{"action":"remind","list":"Súper","remind_at":"<manana>T10:00"}}]

"guardá esta lista como plantilla compras de la semana"
-> [{"intent":"lista_compra","confidence":0.9,"data":{"action":"save_template","item":"Compras de la semana"}}]

"armá la lista de compras de la semana"
-> [{"intent":"lista_compra","confidence":0.9,"data":{"action":"use_template","item":"Compras de la semana"}}]

"lista del super para el sábado"
-> [{"intent":"lista_compra","confidence":0.85,"data":{"action":"show","list":"Súper","target_date":"<sabado>"}}]

"avisame si el blue pasa de 1500"
-> [{"intent":"alerta_dolar","confidence":0.95,"data":{"rate_type":"blue","direction":"above","threshold":1500}}]

"avisame cuando el cripto baje de 1300"
-> [{"intent":"alerta_dolar","confidence":0.92,"data":{"rate_type":"cripto","direction":"below","threshold":1300}}]

"el dolar takenos esta a 1450"
-> [{"intent":"set_takenos_rate","confidence":0.95,"data":{"value":1450}}]

"cuanto vale mi ahorro en dolares?"
-> [{"intent":"dolar","confidence":0.9,"data":{}}]

"cuanto esta el aceite Natura 1.5L?" / "comparame precios de un Samsung A54" / "donde compro mas barato el cafe"
-> [{"intent":"precio","confidence":0.95,"data":{"query":"aceite Natura 1.5L"}}]
precio: {"query":str}  (producto/cosa a buscar precio online y comparar tiendas)

"¿puedo permitirme 80 lucas en salir?"
-> [{"intent":"afford","confidence":0.95,"data":{"afford_amount":80000,"currency":"ARS","afford_category":"Comida afuera"}}]

"me alcanza para comprar 200 dolares?"
-> [{"intent":"afford","confidence":0.92,"data":{"afford_amount":200,"currency":"USD","afford_category":null}}]

"cuanto gaste este mes comparado con el mes pasado?"
-> [{"intent":"consulta","confidence":0.9,"data":{"type":"transacciones","intencion":"total","filters":{"type":"gasto","period":"mes"},"compare_period":"mes_pasado"}}]

"todas las semanas pago 5 lucas de la verduleria con efectivo"
-> [{"intent":"recurrente","confidence":0.9,"data":{"type":"gasto","amount":5000,"currency":"ARS","category":"Comida","account":"Efectivo","description":"Verduleria","frequency":"weekly","next_occurrence":"<HOY>"}}]

"el seguro del auto son 120 lucas una vez al año con naranja"
-> [{"intent":"recurrente","confidence":0.9,"data":{"type":"gasto","amount":120000,"currency":"ARS","account":"Tarjeta Naranja","description":"Seguro auto","frequency":"annual","next_occurrence":"<HOY>"}}]

"recordame todos los dias a las 8 tomar la pastilla"
-> [{"intent":"recordatorio","confidence":0.95,"data":{"text":"Tomar la pastilla","remind_at":"<HOY>T08:00","recurrence":"daily"}}]

"todos los lunes recordame sacar la basura a las 21"
-> [{"intent":"recordatorio","confidence":0.92,"data":{"text":"Sacar la basura","remind_at":"<proximo lunes>T21:00","recurrence":"weekly"}}]"""


def _accs_block(user_id=None):
    accs = list_accounts(user_id=user_id)
    if not accs: return "(no tenes cuentas todavia - crea una con \"crear cuenta X\" o /addcuenta)"
    return "\n".join(f"- {a['name']} ({a['type']})" for a in accs)

def _cats_block():
    return "\n".join(f"- {c['name']} [{c['type']}]" for c in list_categories())

def _others_block(me_id):
    others = [u for u in list_users() if u["id"] != me_id]
    if not others: return "(sin otros usuarios)"
    return ", ".join(u["name"] for u in others)

def build_parser_system(user_id, user_name):
    now = now_local()
    return (PARSER_TEMPLATE
            .replace("__ACCOUNTS__", _accs_block(user_id=user_id))
            .replace("__CATEGORIES__", _cats_block())
            .replace("__TODAY__", now.strftime("%Y-%m-%d"))
            .replace("__NOW__", now.strftime("%H:%M"))
            .replace("__TZ__", TIMEZONE)
            .replace("__DOW__", DIAS_ES[now.weekday()])
            .replace("__ME__", user_name or "Yo")
            .replace("__ME_ID__", str(user_id or 0))
            .replace("__OTHERS__", _others_block(user_id)))


_NUM_RE = r"(\d+(?:[.,]\d+)?)"

def normalize_amounts(text):
    def f(v): return float(v.replace(",", "."))
    t = text
    t = re.sub(rf"{_NUM_RE}\s*palos?\b", lambda m: str(int(f(m.group(1)) * 1000000)), t, flags=re.I)
    t = re.sub(rf"{_NUM_RE}\s*lucas?\b", lambda m: str(int(f(m.group(1)) * 1000)), t, flags=re.I)
    t = re.sub(r"\bmedia\s+luca\b", "500", t, flags=re.I)
    t = re.sub(rf"{_NUM_RE}\s*gambas?\b", lambda m: str(int(f(m.group(1)) * 100)), t, flags=re.I)
    t = re.sub(rf"\b{_NUM_RE}k\b", lambda m: str(int(f(m.group(1)) * 1000)), t, flags=re.I)
    return t


def parse_intent(text, user_id, user_name, prev_consulta=None):
    text = normalize_amounts(text)
    system = build_parser_system(user_id, user_name)

    def call(model, kind="parser"):
        user_content = text
        if prev_consulta:
            user_content = (
                "CONTEXTO (consulta previa del usuario, en JSON). Si este mensaje es una "
                "continuacion corta (ej. 'y de Lisa', 'y la semana pasada'), devolve una "
                "consulta que copie la previa y cambie SOLO el campo mencionado:\n"
                + json.dumps(prev_consulta, ensure_ascii=False)
                + "\n\nMENSAJE: " + text)
        resp = anthropic_client.messages.create(
            model=model, max_tokens=2000,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_content}],
            tools=[PARSER_TOOL],
            tool_choice={"type": "tool", "name": "registrar_acciones"})
        _log_usage(resp, user_id, model, kind)
        for block in resp.content:
            if block.type == "tool_use":
                return block.input.get("acciones") or []
        return []

    acciones = call(MODEL)
    dudoso = (not acciones) or all(
        a.get("intent") == "desconocido" or (a.get("confidence") or 1) < 0.5 for a in acciones)
    if dudoso:
        try:
            retry = call(MODEL_SMART, kind="parser_esc")
            if retry and not all(a.get("intent") == "desconocido" for a in retry):
                acciones = retry
                log.info("Parser escalado a %s", MODEL_SMART)
        except Exception:
            log.exception("Escalado a Sonnet fallo, sigo con Haiku")

    out = []
    for a in acciones:
        intent = a.get("intent", "desconocido")
        out.append({"intent": intent, intent: a.get("data") or {}, "confidence": a.get("confidence")})
    return out


PHOTO_TEMPLATE = """Eres un parser de comprobantes en espanol rioplatense.
Recibis una imagen (ticket, factura, captura de MercadoPago/banco/Naranja/Visa, etc) y extraes transacciones.

CUENTAS DE __ME__ (elegi UNA por transaccion/cuota, exacta):
__ACCOUNTS__

CATEGORIAS:
__CATEGORIES__

══ DETECCION DE CUOTAS (CRITICO) ══
Tu trabajo principal es identificar TODOS los consumos en cuotas visibles en la imagen.

Considera "compra en cuotas" cualquier linea/tarjeta que muestre:
  - "Cuota X/N"  (ej: Cuota 1/6, Cuota 2/9)
  - "X de N cuotas"
  - "Plan en N cuotas"
  - "Cuota X/N" en una columna aparte

INCLUI tanto los consumos NUEVOS del periodo (ej: "Consumos del 28/MAY al 27/JUN")
como los de "Cuotas de consumos anteriores" (compras viejas que siguen activas).
Cada una es un item independiente en el array "cuotas_detectadas".

Si la cuota_actual es > 1, eso significa que la compra es vieja y ya cobraron
cuotas previas (cuota_actual - 1 cuotas ya pasaron). Igual devolve el item;
el bot maneja eso.

CADA cuota detectada debe ser un objeto del array. Si la imagen muestra 2
compras en cuotas (una nueva + una vieja), devolves DOS objetos. Si muestra 5,
devolves CINCO. Es CRITICO no fusionar items ni omitir ninguno.

══ Formato de salida EXCLUSIVO ══
{
  "transacciones": [
    {"type":"gasto"|"ingreso","amount":number,"currency":"ARS"|"USD"|"EUR",
     "category":string,"account":string,"description":string,
     "occurred_at":"YYYY-MM-DDTHH:MM"}
  ],
  "cuotas_detectadas": [
    {"amount":number,"cuotas_total":number,"cuota_actual":number,
     "description":string,"account":string,"category":string,
     "currency":"ARS"|"USD"|"EUR","occurred_at":"YYYY-MM-DDTHH:MM"}
  ]
}

REGLAS de uso de los campos:
- Si la imagen muestra SOLO consumos en cuotas (resumen de tarjeta tipo Naranja):
    transacciones:[]  y cuotas_detectadas:[todos los items en cuotas, uno por cada]
- Si la imagen es un ticket/comprobante UNICO sin cuotas:
    transacciones:[un item]  y cuotas_detectadas:[]
- Si la imagen tiene un ticket con N cuotas (un solo item con monto+cuotas):
    transacciones:[]  y cuotas_detectadas:[ese item]
- Si la imagen tiene una lista mixta (algunos en cuotas, otros no):
    transacciones:[los que NO son en cuotas]  y cuotas_detectadas:[los que SI]

══ Reglas generales ══
- ARS por default. account: priorizar caption del usuario; sino deducir del header/logo.
- amount: el numero tal como aparece, sin asumir si es total o por cuota — el usuario lo aclara despues.
- description: comercio/concepto limpio, max 50 chars. Para "Merpago isaiasemirmaestu" o similar, dejalo asi (es identificador).
- INVERSIONES: oro, bonos, cripto, FCI, ETF, Bonar, AL30, GD30 -> account="Inversiones" si existe.
- occurred_at: fecha del consumo si la ves; sino __TODAY__T12:00.
- Si no detectas nada usable: ambos arrays vacios.
- UN solo JSON, sin texto extra alrededor."""

def parse_photo(image_bytes, caption="", user_id=None, user_name=None):
    now = now_local()
    system = (PHOTO_TEMPLATE
              .replace("__ACCOUNTS__", _accs_block(user_id=user_id))
              .replace("__CATEGORIES__", _cats_block())
              .replace("__TODAY__", now.strftime("%Y-%m-%d"))
              .replace("__ME__", user_name or "Yo"))
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    user_text = "Extrae las transacciones de esta imagen."
    if caption: user_text += f"\n\nContexto del usuario: {caption}"
    resp = anthropic_client.messages.create(model=MODEL, max_tokens=1024, system=system,
        messages=[{"role":"user","content":[
            {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b64}},
            {"type":"text","text":user_text}
        ]}])
    _log_usage(resp, user_id, MODEL, "foto")
    return json.loads(_strip_json(resp.content[0].text))


def fmt_dt(s):
    if 'T' not in s: s += "T00:00"
    d = datetime.fromisoformat(s)
    return f"{DIAS_ES[d.weekday()]} {d.strftime('%d/%m %H:%M')}"

def fmt_d(s):
    d = datetime.fromisoformat(s if 'T' in s else s+"T00:00")
    return f"{DIAS_ES[d.weekday()]} {d.strftime('%d/%m')}"


def _reemit_recurring_reminder(app_or_jobqueue, fired_row):
    """Si el recordatorio que acaba de disparar es recurrente, crea la proxima
    ocurrencia (nueva fila fired=0) y la agenda. fired_row necesita: text,
    remind_at, recurrence, user_id, telegram_id."""
    try:
        keys = fired_row.keys()
    except Exception:
        keys = []
    rec = fired_row["recurrence"] if "recurrence" in keys else None
    if not rec:
        return
    nxt = recurrence.next_reminder_at(rec, fired_row["remind_at"])
    if not nxt:
        return
    lid = fired_row["list_id"] if "list_id" in keys else None
    new_id = save_recordatorio(fired_row["text"], nxt, fired_row["user_id"],
                               source="recurrente", raw_id=None, list_id=lid)
    with db() as c:
        c.execute("UPDATE recordatorios SET recurrence=? WHERE id=?", (rec, new_id))
    jq = getattr(app_or_jobqueue, "job_queue", app_or_jobqueue)
    chat_id = fired_row["telegram_id"] or (ALLOWED_USER_IDS[0] if ALLOWED_USER_IDS else None)
    if chat_id:
        schedule_reminder(jq, new_id, fired_row["text"], nxt, chat_id)


async def send_reminder(context):
    data = context.job.data
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT r.id, r.text, r.remind_at, r.recurrence, r.user_id, r.fired, r.list_id, u.telegram_id AS telegram_id "
        "FROM recordatorios r LEFT JOIN users u ON u.id=r.user_id WHERE r.id=?",
        (data["rem_id"],)).fetchone()
    if row and row["fired"]:
        conn.close(); return
    try:
        body, kb = f"⏰ {data['text']}", None
        if row and row["list_id"]:
            try:
                ltext, kb = _render_shopping(row["list_id"])
                body = f"⏰ {data['text']}\n\n{ltext}"
            except Exception:
                log.exception("render lista en send_reminder %s", data.get("rem_id"))
        await context.bot.send_message(chat_id=data["chat_id"], text=body, reply_markup=kb)
    finally:
        conn.execute("UPDATE recordatorios SET fired=1 WHERE id=?", (data["rem_id"],))
        conn.commit(); conn.close()
    if row:
        try:
            _reemit_recurring_reminder(context.application, row)
        except Exception:
            log.exception("reemit reminder (run_once) %s", row["id"])

def schedule_reminder(job_queue, rem_id, text, remind_at_str, chat_id):
    dt = parse_local(remind_at_str)
    delay = (dt - now_local()).total_seconds()
    if delay <= 0: return None
    return job_queue.run_once(callback=send_reminder, when=delay,
        data={"rem_id":rem_id,"text":text,"chat_id":chat_id}, name=f"reminder_{rem_id}")

def reschedule_pending(app):
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute("""SELECT r.id, r.text, r.remind_at, u.telegram_id
                           FROM recordatorios r LEFT JOIN users u ON u.id=r.user_id
                           WHERE r.fired=0 ORDER BY r.remind_at""").fetchall()
    conn.close()
    n=0
    for r in rows:
        chat_id = r['telegram_id'] or (ALLOWED_USER_IDS[0] if ALLOWED_USER_IDS else None)
        if chat_id and schedule_reminder(app.job_queue, r['id'], r['text'], r['remind_at'], chat_id):
            n+=1
    log.info("Recordatorios reagendados: %d", n)


async def recurring_daily(context):
    today_str = now_local().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    due = conn.execute("""SELECT r.*, u.telegram_id AS owner_tg
                          FROM recurring r LEFT JOIN users u ON u.id=r.user_id
                          WHERE r.active=1 AND r.next_occurrence <= ?""", (today_str,)).fetchall()
    conn.close()
    for r in due:
        try:
            conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
            acc = conn.execute("SELECT name FROM accounts WHERE id=?", (r['account_id'],)).fetchone()
            cat_row = conn.execute("SELECT name FROM categories WHERE id=?", (r['category_id'],)).fetchone() if r['category_id'] else None
            occurred_at = today_str + "T09:00"
            new_fired = (r['installments_fired'] or 0) + 1
            total = r['total_installments']
            cuota_str = f" (cuota {new_fired}/{total})" if total else ""
            desc_full = r['description'] + cuota_str
            cur = conn.execute(
                "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,recurring_id,user_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (r['type'], r['amount'], r['currency'], r['account_id'], r['category_id'],
                 desc_full, occurred_at, r['id'], r['user_id']))
            tx_id = cur.lastrowid
            freq = r['frequency'] if r['frequency'] in ('monthly', 'weekly', 'annual') else 'monthly'
            next_dt = recurrence.next_occurrence(freq, r['next_occurrence'], r['day_of_month'])
            if total and new_fired >= total:
                conn.execute("UPDATE recurring SET active=0, installments_fired=? WHERE id=?", (new_fired, r['id']))
            else:
                conn.execute("UPDATE recurring SET next_occurrence=?, installments_fired=? WHERE id=?", (next_dt, new_fired, r['id']))
            conn.commit(); conn.close()
            sign = "💸" if r['type'] == 'gasto' else "💰"
            cierre = "\n\n✅ Ultima cuota cobrada, recurrente finalizada." if (total and new_fired >= total) else ""
            msg = (f"🔁 Recurrente generada{cuota_str}\n{sign} {r['amount']:,.2f} {r['currency']} — {r['description']}\n"
                   f"📂 {acc['name']}")
            if cat_row: msg += f" · 🏷️ {cat_row['name']}"
            msg += cierre
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar (no se cobro)", callback_data=f"txcancel:{tx_id}")]])
            chat_id = r['owner_tg'] or (ALLOWED_USER_IDS[0] if ALLOWED_USER_IDS else None)
            if chat_id:
                await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=kb)
        except Exception:
            log.exception("Error procesando recurrente %s", r['id'])


async def callback_handler(update, context):
    q = update.callback_query
    parts = q.data.split(":", 1)
    if len(parts) != 2:
        await q.answer(); return
    action, arg = parts
    base_text = q.message.text or ""

    # Aislamiento: todas las acciones por id se acotan al HOGAR del que clickea
    # (callback_data lo controla el cliente → si no se filtra, es IDOR cross-usuario).
    if action == "tdone":
        try:
            tid = int(arg); m = household_member_ids(current_user_id(update)); ph = ",".join("?" for _ in m)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute(f"UPDATE tareas SET status='hecha', completed_at=datetime('now') WHERE id=? AND user_id IN ({ph})", [tid]+m)
            conn.commit(); n = cur.rowcount; conn.close()
            await q.answer(f"✓ Tarea #{tid} hecha" if n else "No es tuya", show_alert=not n)
        except Exception:
            log.exception("tdone"); await q.answer("Error", show_alert=True)
        return

    if action == "tdel":
        try:
            tid = int(arg); m = household_member_ids(current_user_id(update)); ph = ",".join("?" for _ in m)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute(f"DELETE FROM tareas WHERE id=? AND user_id IN ({ph})", [tid]+m)
            conn.commit(); n = cur.rowcount; conn.close()
            await q.answer(f"× Tarea #{tid} borrada" if n else "No es tuya", show_alert=not n)
        except Exception:
            log.exception("tdel"); await q.answer("Error", show_alert=True)
        return

    if action == "txdel":
        try:
            tid = int(arg); m = household_member_ids(current_user_id(update)); ph = ",".join("?" for _ in m)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute(f"DELETE FROM transactions WHERE id=? AND user_id IN ({ph})", [tid]+m)
            conn.commit(); n = cur.rowcount; conn.close()
            if n:
                await q.answer("🗑️ Borrada"); await q.edit_message_text(base_text + "\n\n🗑️ Borrada.")
            else:
                await q.answer("No es tuya", show_alert=True)
        except Exception:
            log.exception("txdel"); await q.answer("Error", show_alert=True)
        return

    if action == "rectoggle":
        try:
            rid = int(arg); m = household_member_ids(current_user_id(update)); ph = ",".join("?" for _ in m)
            conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
            row = conn.execute(f"SELECT active FROM recurring WHERE id=? AND user_id IN ({ph})", [rid]+m).fetchone()
            if row:
                conn.execute(f"UPDATE recurring SET active=? WHERE id=? AND user_id IN ({ph})", [0 if row['active'] else 1, rid]+m)
                conn.commit(); conn.close(); await q.answer("Estado cambiado")
            else:
                conn.close(); await q.answer("No es tuya", show_alert=True)
        except Exception:
            log.exception("rectoggle"); await q.answer("Error", show_alert=True)
        return

    if action == "recdel":
        try:
            rid = int(arg); m = household_member_ids(current_user_id(update)); ph = ",".join("?" for _ in m)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute(f"DELETE FROM recurring WHERE id=? AND user_id IN ({ph})", [rid]+m)
            conn.commit(); n = cur.rowcount; conn.close()
            await q.answer("🗑️ Borrada" if n else "No es tuya", show_alert=not n)
        except Exception:
            log.exception("recdel"); await q.answer("Error", show_alert=True)
        return

    if action == "remdel":
        try:
            rid = int(arg); m = household_member_ids(current_user_id(update)); ph = ",".join("?" for _ in m)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute(f"UPDATE recordatorios SET fired=1 WHERE id=? AND user_id IN ({ph})", [rid]+m)
            conn.commit(); n = cur.rowcount; conn.close()
            await q.answer("⏰ Cancelado" if n else "No es tuyo", show_alert=not n)
        except Exception:
            log.exception("remdel"); await q.answer("Error", show_alert=True)
        return

    if action == "subagendar":
        try:
            uid = current_user_id(update)
            amt_s, cur, desc = arg.split("|", 2)
            amount = float(amt_s)
            today = now_local()
            r = {"type": "gasto", "amount": amount, "currency": cur,
                 "account": _first_account_name(uid), "category": None,
                 "description": desc, "frequency": "monthly",
                 "day_of_month": today.day,
                 "next_occurrence": today.strftime("%Y-%m-%d"),
                 "total_installments": None}
            save_recurring(r, None, uid, fire_immediately=False)
            await q.answer("📌 Agendada como recurrente mensual")
            await q.edit_message_text((q.message.text or "") +
                f"\n\n✅ Agendada como recurrente mensual (~{amount:,.0f} {cur}). "
                f"Editá la cuenta/categoría con /recurrentes si hace falta.")
        except Exception:
            log.exception("subagendar"); await q.answer("Error al agendar", show_alert=True)
        return

    if action == "cardpay":
        try:
            acc_id = int(arg)
            today = now_local().date()
            m = household_member_ids(current_user_id(update)); ph = ",".join("?" for _ in m)
            with db() as c:
                card = c.execute(f"SELECT * FROM accounts WHERE id=? AND user_id IN ({ph})", [acc_id]+m).fetchone()
            if not card:
                await q.answer("Cuenta no encontrada", show_alert=True); return
            d = vencimientos.calcular_vencimiento(DB_PATH, dict(card), today)
            cerrado = [t for t in (d.get("ciclo_cerrado") or []) if t.get("total")]
            if not cerrado:
                await q.answer("No hay saldo cerrado para pagar.", show_alert=True); return
            cat = get_category_by_name("Transferencia")
            occ = now_local().strftime("%Y-%m-%dT%H:%M")
            partes = []
            with db() as c:
                for t in cerrado:
                    c.execute(
                        "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,user_id) "
                        "VALUES ('ingreso',?,?,?,?,?,?,?)",
                        (t["total"], t["currency"], acc_id,
                         cat["id"] if cat else None,
                         f"Pago tarjeta {card['name']}", occ, card["user_id"]))
                    partes.append(f"{t['total']:,.2f} {t['currency']}")
            await q.answer("✅ Pago registrado")
            await q.edit_message_text(base_text + "\n\n✅ Pagado: " + " + ".join(partes))
        except Exception:
            log.exception("cardpay"); await q.answer("Error", show_alert=True)
        return

    if action == "lscheck":
        try:
            iid = int(arg)
            m = household_member_ids(current_user_id(update)); ph = ",".join("?" for _ in m)
            with db() as c:
                row = c.execute(
                    f"SELECT s.done, s.list_id FROM shopping_items s JOIN lists l ON l.id=s.list_id "
                    f"WHERE s.id=? AND l.owner_user_id IN ({ph})", [iid]+m).fetchone()
                if not row:
                    await q.answer("Ese item ya no esta"); return
                new_done = 0 if row["done"] else 1
                c.execute(
                    "UPDATE shopping_items SET done=?, "
                    "done_at=CASE WHEN ?=1 THEN datetime('now') ELSE NULL END WHERE id=?",
                    (new_done, new_done, iid))
                lid = row["list_id"]
            await q.answer("✅ Tachado" if new_done else "↩️ Restaurado")
            text, kb = _render_shopping(lid)
            try:
                await q.edit_message_text(text, reply_markup=kb)
            except Exception:
                pass  # "message is not modified" u otro -> ignorar
        except Exception:
            log.exception("lscheck"); await q.answer("Error", show_alert=True)
        return

    if action == "lsclear":
        try:
            lid = int(arg)
            m = household_member_ids(current_user_id(update)); ph = ",".join("?" for _ in m)
            with db() as c:
                if not c.execute(f"SELECT 1 FROM lists WHERE id=? AND owner_user_id IN ({ph})", [lid]+m).fetchone():
                    await q.answer("No es tuya", show_alert=True); return
                c.execute("DELETE FROM shopping_items WHERE list_id=? AND done=1", (lid,))
            await q.answer("🧹 Listo")
            text, kb = _render_shopping(lid)
            try:
                await q.edit_message_text(text, reply_markup=kb)
            except Exception:
                pass
        except Exception:
            log.exception("lsclear"); await q.answer("Error", show_alert=True)
        return

    await q.answer()

    # >>> photo cuotas patch
    # >>> photo cuotas v5
    if action == "phct":
        try:
            choice, op_id = arg.split(":", 1)
        except ValueError:
            await q.answer(); return
        op = PENDING_OPS.pop(op_id, None)
        if not op:
            await q.edit_message_text(base_text + "\n\n⚠️ Esta operación ya expiró o se resolvió.")
            return
        if choice == "cancel":
            await q.edit_message_text(base_text + "\n\n❌ Cancelado.")
            return
        if choice == "skip":
            await q.edit_message_text(base_text + "\n\n⏭ Salteada (no se cargó nada).")
            return

        amt = op["amount"]; n = int(op["cuotas"])
        cuota_actual = max(1, int(op.get("cuota_actual", 1) or 1))
        if choice == "total":
            per_cuota = amt / n; total = amt
            interp = f"interpretado como TOTAL → ${per_cuota:,.2f} por cuota × {n}"
        elif choice == "cuota":
            per_cuota = amt; total = amt * n
            interp = f"interpretado como CADA CUOTA → ${per_cuota:,.2f} × {n} = ${total:,.2f}"
        else:
            await q.answer(); return

        try:
            acc = get_account_by_name(op.get("account",""), user_id=op["user_id"])
            if not acc:
                await q.edit_message_text(
                    base_text + f"\n\n❌ No tengo la cuenta '{op.get('account','')}' creada. "
                    f"Creala con /addcuenta y volvé a mandar la foto.")
                return
            cat = get_category_by_name(op.get("category","Otros"))

            # next_occurrence = VENCIMIENTO del cierre donde postea la compra (no el cierre).
            closing_day = acc.get("closing_day")
            due_day = acc.get("due_day")
            day = due_day or closing_day or now_local().day
            try:
                import vencimientos as _v
                if closing_day and due_day:
                    _venc = _v.venc_de_cuota(closing_day, due_day, now_local().date())
                    next_occ_str = _venc.strftime("%Y-%m-%d")
                    day = due_day
                elif closing_day:  # sin vencimiento cargado, caemos al cierre (como antes)
                    next_occ_str = _v.proxima_fecha_para_cuota(closing_day, now_local().date()).strftime("%Y-%m-%d")
                    day = closing_day
                else:
                    next_occ_str = compute_next_monthly(now_local().strftime("%Y-%m-%d"), day)
            except Exception:
                next_occ_str = compute_next_monthly(now_local().strftime("%Y-%m-%d"), day)

            # Insertar el recurrente. installments_fired = cuota_actual - 1
            # (las anteriores se asumen pagadas en meses previos, sea 0 o más).
            # NO creamos transaccion hoy: el daily-job cargará la cuota
            # correspondiente cuando se cumpla next_occurrence (fecha de cierre).
            conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
            installments_fired_initial = cuota_actual - 1
            cur = conn.execute(
                "INSERT INTO recurring (type,amount,currency,account_id,category_id,description,frequency,day_of_month,next_occurrence,total_installments,installments_fired,raw_message_id,user_id) "
                "VALUES (?,?,?,?,?,?,'monthly',?,?,?,?,?,?)",
                ("gasto", per_cuota, op.get("currency","ARS"), acc["id"],
                 cat["id"] if cat else None, op.get("description","Compra en cuotas"),
                 day, next_occ_str, n, installments_fired_initial,
                 op.get("raw_id"), op["user_id"]))
            rid = cur.lastrowid
            conn.commit(); conn.close()

            restantes = n - installments_fired_initial  # cuotas que aun van a caer (la proxima + las siguientes)
            if cuota_actual == 1:
                explain = (f"   Cuota <b>1/{n}</b> es la próxima — cae el <b>{next_occ_str}</b> (vencimiento de la tarjeta).\n"
                           f"   Quedan {restantes} cuotas en total ({restantes-1} más después).")
            else:
                explain = (f"   Cuotas 1 a {cuota_actual-1}: asumidas como ya pagadas en meses anteriores.\n"
                           f"   Cuota <b>{cuota_actual}/{n}</b> es la próxima — cae el <b>{next_occ_str}</b>.\n"
                           f"   Quedan {restantes} cuotas por delante.")

            msg = (f"✅ Cargado como recurrente.\n"
                   f"   {interp}\n"
                   f"{explain}\n"
                   f"   Recurrente #{rid}")
            await q.edit_message_text(base_text + "\n\n" + msg, parse_mode="HTML")
        except Exception as e:
            log.exception("phct save fail")
            await q.edit_message_text(base_text + f"\n\n❌ Error al guardar: {e}")
        return

    if action == "txcancel":
        try:
            tx_id = int(arg)
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
            conn.commit(); conn.close()
            await q.edit_message_text(base_text + "\n\n❌ Cancelado.")
        except Exception:
            log.exception("Cancel fail")
    elif action == "movok":
        op = PENDING_OPS.pop(arg, None)
        if not op: await q.edit_message_text(base_text + "\n\n⚠️ Operacion expirada."); return
        n = apply_move(op['ids'], op.get('target_account_id'), op.get('target_category_id'))
        await q.edit_message_text(base_text + f"\n\n✅ Movidas {n} transacciones.")
    elif action == "movno":
        PENDING_OPS.pop(arg, None)
        await q.edit_message_text(base_text + "\n\n❌ Cancelado.")
    elif action == "delok":
        op = PENDING_OPS.pop(arg, None)
        if not op: await q.edit_message_text(base_text + "\n\n⚠️ Operacion expirada."); return
        n = apply_delete(op['ids'])
        await q.edit_message_text(base_text + f"\n\n🗑️ Borradas {n} transacciones.")
    elif action == "delno":
        PENDING_OPS.pop(arg, None)
        await q.edit_message_text(base_text + "\n\n❌ Cancelado.")
    elif action == "saldarok":
        op = PENDING_OPS.pop(arg, None)
        if not op:
            await q.edit_message_text(base_text + "\n\n⚠️ Operacion expirada."); return
        n = settle_all_shared(op["me_id"], op["other_id"])
        await q.edit_message_text(
            base_text + f"\n\n✅ Saldados {n} gasto(s). Estan a mano \U0001F91D")
    elif action == "saldarno":
        PENDING_OPS.pop(arg, None)
        await q.edit_message_text(base_text + "\n\n❌ Cancelado.")


async def notify_user(app, telegram_id, text, reply_markup=None):
    """Push proactivo a un usuario (helper compartido de features)."""
    try:
        await app.bot.send_message(chat_id=telegram_id, text=text, reply_markup=reply_markup)
    except Exception:
        log.exception("notify_user fallo a %s", telegram_id)

def each_user():
    """[(user_id, telegram_id), ...] de usuarios activos."""
    with db() as c:
        return [(r["id"], r["telegram_id"]) for r in
                c.execute("SELECT id, telegram_id FROM users WHERE active=1").fetchall()]

def _wa_only(update):
    """True si el usuario llega por WhatsApp sin Telegram vinculado (telegram_id negativo)."""
    try:
        return int(update.effective_user.id) < 0
    except Exception:
        return False

async def _send_wa_reminder_notice(update):
    """Avisa a un usuario de WhatsApp que los recordatorios por WA están en desarrollo y le
    ofrece la web (push) o Telegram con un deep-link que vincula las cuentas al instante."""
    u = get_user_by_tg(update.effective_user.id)
    dl = None
    if u:
        try:
            code = gen_referral_code(6).upper()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE users SET link_code=?, link_code_exp=datetime('now','+1 day') WHERE id=?",
                         (code, u["id"]))
            conn.commit(); conn.close()
            bot_un = os.environ.get("BOT_USERNAME", "").lstrip("@")
            if bot_un:
                dl = f"https://t.me/{bot_un}?start=link_{code}"
        except Exception:
            log.exception("wa reminder deeplink")
    msg = ("📌 Lo guardé, pero ojo: los avisos de recordatorios *por WhatsApp* todavía están en "
           "desarrollo, así que por ahora no te puedo avisar acá cuando llegue la hora.\n\n"
           "Para recibir el aviso, elegí una:\n"
           f"• 🌐 Abrí la web, instalala y activá las notificaciones:\n{APP_URL}\n")
    if dl:
        msg += ("\n• 📲 O pasate a Telegram — te aviso ahí y te dejo todo vinculado a esta misma "
                f"cuenta automáticamente:\n{dl}\n\n(El link vale 1 día.)")
    await update.message.reply_text(msg)

async def on_error(update, context):
    """Error handler global: loguea y avisa al dueno por Telegram (observabilidad sin infra nueva)."""
    log.exception("Error no manejado", exc_info=context.error)
    try:
        if ALLOWED_USER_IDS:
            await context.bot.send_message(
                chat_id=ALLOWED_USER_IDS[0],
                text=f"⚠️ Error interno del asistente: {type(context.error).__name__}")
    except Exception:
        log.exception("on_error: no pude avisar al dueno")


async def post_init(app):
    reschedule_pending(app)
    try:
        await app.bot.set_my_commands([
            ("resumen", "Resumen del mes"),
            ("movimientos", "Ultimos movimientos"),
            ("cuentas", "Cuentas y balances"),
            ("recurrentes", "Pagos recurrentes"),
            ("vencimientos", "Proximos pagos de tarjetas"),
            ("tareas", "Tareas pendientes"),
            ("done", "Marcar tarea hecha (/done N)"),
            ("pendientes", "Recordatorios proximos"),
            ("habitos", "Habitos ultimos 7 dias"),
            ("notas", "Ultimas notas"),
            ("buscar", "Buscar texto (/buscar ...)"),
            ("cotizacion", "Cotizacion del dolar"),
            ("patrimonio", "Patrimonio neto (ARS + USD)"),
            ("dolar", "Tu ahorro en USD (Takenos)"),
            ("precio", "Comparar precios online"),
            ("orden", "Ver orden medica de un turno"),
            ("addcuenta", "Crear cuenta"),
            ("proximospagos", "Calendario de pagos (30 dias)"),
            ("balance", "Quien debe a quien (pareja)"),
            ("saldar", "Saldar gastos compartidos"),
            ("metas", "Metas de ahorro"),
            ("suscripciones", "Suscripciones detectadas"),
            ("lista", "Ver una lista (/lista [nombre])"),
            ("listas", "Todas tus listas"),
            ("meta", "Meta semanal de un habito"),
            ("password", "Cambiar clave del dashboard"),
            ("help", "Ayuda"),
        ])
    except Exception:
        log.exception("set_my_commands fallo (no critico)")


async def start_cmd(update, context):
    code0 = (context.args[0].strip() if getattr(context, "args", None) else "")
    # Deep-link de vinculación (lo abre un usuario de WhatsApp en Telegram → une las cuentas).
    if code0.startswith("link_"):
        ok, name, reason = link_telegram_via_code(code0[5:], update.effective_user.id)
        if ok:
            await update.message.reply_text(
                f"✅ ¡Listo{(' ' + name) if name else ''}! Vinculé tu WhatsApp con Telegram. "
                "Ahora te aviso los recordatorios por acá y ves lo mismo en los dos lados.")
        elif reason == "already_telegram":
            await update.message.reply_text(
                "Ya tenés una cuenta en Telegram 🙂 Para unirla con tu WhatsApp, "
                "mandá /vincular acá y seguí los pasos.")
        else:
            await update.message.reply_text(
                "Ese link de vinculación venció o no es válido 😕 Pedí uno nuevo desde WhatsApp "
                "(mandá «recordame ...» y te paso un link nuevo).")
        return
    u = get_user_by_tg(update.effective_user.id)
    if u:
        await update.message.reply_text(
            f"Hola {u['name']}. Mandame texto, audios o fotos:\n\n"
            "💸 «pague 1000 coca cola con MP» / foto de un ticket\n"
            "💰 «me pagaron 500 USD takenos sueldo»\n"
            "🔁 «agenda Movistar 7000 todos los 10 con MP»\n"
            "🏦 «crear cuenta Visa nueva tipo credito»\n"
            "📊 «cuanto gastamos los dos este mes?»\n"
            "📅 «cena con Ana viernes 21»\n"
            "⏰ «recordame manana 9 llamar al banco»\n"
            "✅ «tengo que pagar la luz»\n"
            "💪 «hice 30 min de ejercicio»\n"
            "📓 «anota: idea para X»\n\n"
            "Comandos: /resumen /cuentas /recurrentes /movimientos /borrar N\n"
            "/tareas /done N /habitos /pendientes /notas\n"
            "/password <nueva> · /addcuenta <nombre> [tipo]\n"
            "👨‍👩‍👧 /invitar — sumá a tu familia (comparten todo)")
        return
    # No registrado: ¿viene con código de invitación? (deep-link t.me/<bot>?start=<code>)
    code = (context.args[0].strip() if getattr(context, "args", None) else "")
    # Invitación a la FAMILIA: el usuario nuevo se UNE al hogar del que invita (comparten todo).
    if code.startswith("fam_"):
        inviter = get_user_by_referral_code(code[4:])
        if inviter:
            cap = plan_limits(household_plan(inviter["id"]))["household"]
            if len(household_member_ids(inviter["id"])) >= cap:
                await update.message.reply_text(
                    f"El hogar de {inviter['name']} ya está completo (hasta {cap} integrante(s) en su plan). "
                    "Que actualice el plan para sumar a más.")
                return
            hh = inviter.get("household_id") or inviter["id"]
            new_user, temp_pw = onboard_user(
                "telegram", update.effective_user.id,
                update.effective_user.first_name, inviter["id"], household_id=hh)
            msg = (f"🎉 ¡Bienvenido/a a Yumi, {new_user['name']}! Te sumaste a la familia de {inviter['name']} — "
                   "van a compartir listas, gastos y agenda.\n\n"
                   "Mandame texto, audios o fotos:\n"
                   "💸 «pagué 1000 de café con débito»\n"
                   "📅 «cena con Ana el viernes 21»\n"
                   "⏰ «recordame mañana 9 llamar al banco»\n\n")
            if temp_pw:
                msg += (f"🌐 *App web de Yumi:* {APP_URL}\n"
                        f"Entrá con usuario *{new_user['username']}* y clave temporal `{temp_pw}` "
                        f"(cambiala con /password <nueva>). También funciona acá en el chat.")
            await update.message.reply_text(msg, parse_mode="Markdown")
            return
        await send_register_prompt(update); return
    if code:
        referrer = get_user_by_referral_code(code)
        if referrer and can_invite(referrer):
            new_user, temp_pw = onboard_user(
                "telegram", update.effective_user.id,
                update.effective_user.first_name, referrer["id"])
            msg = (f"🎉 ¡Bienvenido/a a Yumi, {new_user['name']}! Te invitó {referrer['name']}.\n\n"
                   "Soy tu asistente: mandame texto, audios o fotos.\n"
                   "💸 «pagué 1000 de café con débito»\n"
                   "📅 «cena con Ana el viernes 21»\n"
                   "⏰ «recordame mañana 9 llamar al banco»\n\n")
            if temp_pw:
                msg += (f"🌐 *App web de Yumi:* {APP_URL}\n"
                        f"Entrá con usuario *{new_user['username']}* y clave temporal `{temp_pw}` "
                        f"(cambiala con /password <nueva>). El bot también funciona acá en el chat, sin necesidad de entrar a la web.")
            await update.message.reply_text(msg, parse_mode="Markdown")
            return
    await send_register_prompt(update)


async def invitar_cmd(update, context):
    """Le da al usuario su link para invitar a su familia (se unen a SU hogar y comparten todo).
    Respeta el plan: cuántos integrantes permite y cuántos lugares quedan."""
    if not is_allowed(update):
        await send_register_prompt(update); return
    u = get_user_by_tg(update.effective_user.id)
    if not u:
        await send_register_prompt(update); return
    plan = household_plan(u["id"])
    cap = plan_limits(plan)["household"]
    current = len(household_member_ids(u["id"]))
    if cap <= 1:
        await update.message.reply_text(
            "Tu plan actual es individual 🙂 Para compartir con tu familia (listas, gastos, agenda), "
            "actualizá a un plan *pareja* o superior.", parse_mode="Markdown"); return
    if current >= cap:
        await update.message.reply_text(
            f"Tu hogar ya está completo: {current}/{cap} integrantes para tu plan ({plan}). "
            "Actualizá el plan para sumar a más."); return
    code = u.get("referral_code") or ""
    try:
        bot_un = (await context.bot.get_me()).username
    except Exception:
        bot_un = os.environ.get("BOT_USERNAME", "").lstrip("@")
    if not (bot_un and code):
        await update.message.reply_text("No pude generar tu link ahora. Probá de nuevo en un momento."); return
    link = f"https://t.me/{bot_un}?start=fam_{code}"
    slots = cap - current
    await update.message.reply_text(
        "👨‍👩‍👧 *Sumá a tu familia a Yumi*\n\n"
        f"Te queda{'n' if slots != 1 else ''} {slots} lugar{'es' if slots != 1 else ''} en tu hogar (plan {plan}).\n"
        "Mandales este link; cuando lo abran, comparten con vos listas, gastos y agenda:\n\n"
        f"{link}", parse_mode="Markdown")


async def vincular_cmd(update, context):
    """Vincula el WhatsApp del usuario a ESTA cuenta de Telegram (mismo dato en los dos canales)."""
    if not is_allowed(update):
        await send_register_prompt(update); return
    u = get_user_by_tg(update.effective_user.id)
    if not u:
        await send_register_prompt(update); return
    code = gen_referral_code(6).upper()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET link_code=?, link_code_exp=datetime('now','+15 minutes') WHERE id=?", (code, u["id"]))
    conn.commit(); conn.close()
    num = os.environ.get("WHATSAPP_NUMBER", "").strip().lstrip("+")
    msg = ("🔗 *Vincular tu WhatsApp con esta cuenta*\n\n"
           "Mandá este mensaje al WhatsApp de Yumi:\n\n"
           f"`vincular {code}`\n\n"
           "Así vas a ver lo mismo en Telegram y en WhatsApp. (El código vence en 15 minutos.)")
    if num:
        msg += f"\n\nO tocá: https://wa.me/{num}?text=vincular%20{code}"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def help_cmd(update, context):
    if not is_allowed(update): return
    await update.message.reply_text(
        "📚 Comandos\n\n"
        "💸 /movimientos [N] · /tx N · /borrar N · /cuentas · /cotizacion\n"
        "🔁 /recurrentes\n✅ /tareas · /done N\n💪 /habitos\n⏰ /pendientes\n📓 /notas [busqueda]\n"
        "🔍 /buscar TEXTO · 📊 /resumen\n"
        "🏦 /addcuenta <nombre> [tipo] · 🔑 /password <nueva>\n\n"
        "Natural:\n  «pague 1000 con MP»\n  «cuanto gastamos los dos este mes?»\n"
        "  «mostrame mis ultimas 3 transacciones»\n  «crear cuenta Visa Galicia»")


async def password_cmd(update, context):
    if not is_allowed(update): return
    u = current_user(update)
    if not u:
        await update.message.reply_text("No estas registrado en la DB."); return
    if not context.args:
        await update.message.reply_text(f"Usa: /password <nueva contrasena>\nTu usuario web: {u['username']}"); return
    new = " ".join(context.args).strip()
    if len(new) < 6:
        await update.message.reply_text("Minimo 6 caracteres."); return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new), u['id']))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Password actualizada para «{u['username']}».")


async def addcuenta_cmd(update, context):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Usa: /addcuenta <nombre> [efectivo|billetera|credito|banco|inversion]"); return
    u = current_user(update)
    tipo = "efectivo"
    args = list(context.args)
    if args and args[-1].lower() in ("efectivo","billetera","credito","crédito","banco","inversion","inversión"):
        tipo = args.pop().lower().replace("é","e").replace("ó","o")
    nombre = " ".join(args).strip()
    if not nombre: await update.message.reply_text("Falta el nombre."); return
    existing = get_account_by_name(nombre, user_id=u['id'])
    if existing and _norm_name(existing['name']) == _norm_name(nombre):
        await update.message.reply_text(f"Ya tenes una cuenta llamada «{existing['name']}»."); return
    iconos = {"efectivo":"💵","billetera":"💳","credito":"🏦","banco":"🏛️","inversion":"📈"}
    create_account(u['id'], nombre, type_=tipo, icon=iconos.get(tipo,"💳"))
    await update.message.reply_text(f"✅ Cuenta «{nombre}» ({tipo}) creada.")




# >>> shared patch
# # >>> compartir v2
async def compartir_cmd(update, context):
    if not is_allowed(update): return
    args = list(context.args or [])
    uid = current_user_id(update)

    def help_msg():
        return ("📋 Uso de /compartir:\n\n"
                "  /compartir todas\n"
                "      → comparte TODAS tus tareas pendientes\n"
                "  /compartir tarea <id>\n"
                "  /compartir nota <id>\n"
                "      → comparte una sola con Lisa/Emir\n"
                "  /compartir off tarea <id>\n"
                "  /compartir off nota <id>\n"
                "      → deja de compartirla")

    if not args:
        await update.message.reply_text(help_msg()); return

    a0 = args[0].lower()

    # /compartir todas
    if a0 == "todas":
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        pendings = conn.execute(
            "SELECT id, text, COALESCE(shared,0) AS sh FROM tareas "
            "WHERE status='pendiente' AND user_id=?", (uid,)).fetchall()
        cur = conn.execute("UPDATE tareas SET shared=1 WHERE user_id=? AND status='pendiente'", (uid,))
        n = cur.rowcount
        conn.commit(); conn.close()
        if not pendings:
            await update.message.reply_text("No tenes tareas pendientes propias para compartir."); return
        already = sum(1 for p in pendings if p["sh"])
        nuevas = n - 0  # todas pasan a 1
        preview = "\n".join(f"  👥 #{p['id']} {p['text']}" for p in pendings[:12])
        extra = f"\n  …y {len(pendings)-12} mas" if len(pendings) > 12 else ""
        msg = (f"✅ Compartidas {len(pendings)} tareas con el otro usuario.\n"
               f"(ya eran compartidas: {already})\n\n{preview}{extra}")
        await update.message.reply_text(msg); return

    # /compartir off ...
    if a0 == "off":
        if len(args) < 3:
            await update.message.reply_text("Uso: /compartir off <tarea|nota> <id>"); return
        kind, raw_id = args[1].lower(), args[2].lstrip("#")
        target_state = 0
    else:
        if len(args) < 2:
            await update.message.reply_text(help_msg()); return
        kind, raw_id = a0, args[1].lstrip("#")
        target_state = 1

    try: tid = int(raw_id)
    except ValueError:
        await update.message.reply_text(f"El ID '{raw_id}' no es numero."); return
    if kind not in ("tarea", "tareas", "nota", "notas"):
        await update.message.reply_text("Tipo invalido. Usa: tarea o nota."); return

    table = "tareas" if kind.startswith("tarea") else "notas"
    label_singular = "tarea" if table == "tareas" else "nota"

    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute(
        f"SELECT id, text, user_id, COALESCE(shared,0) AS sh FROM {table} WHERE id=?",
        (tid,)).fetchone()
    if not row:
        conn.close()
        await update.message.reply_text(f"No encontre {label_singular} #{tid}."); return
    if row["user_id"] != uid and row["sh"] != 1:
        conn.close()
        await update.message.reply_text(
            f"❌ La {label_singular} #{tid} no es tuya ni esta compartida, no puedo tocarla."); return
    if row["sh"] == target_state:
        conn.close()
        estado = "compartida" if target_state else "privada"
        await update.message.reply_text(f"ℹ️ #{tid} ya estaba {estado}, no cambia nada."); return

    conn.execute(f"UPDATE {table} SET shared=? WHERE id=?", (target_state, tid))
    conn.commit(); conn.close()

    preview = row["text"][:80] + ("…" if len(row["text"]) > 80 else "")
    if target_state:
        await update.message.reply_text(f"👥 {label_singular.capitalize()} #{tid} ahora es compartida.\n   «{preview}»")
    else:
        await update.message.reply_text(f"🔒 {label_singular.capitalize()} #{tid} vuelve a ser privada.\n   «{preview}»")


async def compartidos_cmd(update, context):
    """Lista todo lo compartido entre ambos usuarios."""
    if not is_allowed(update): return
    uid = current_user_id(update)
    _m = household_member_ids(uid); _mph = ",".join("?" for _ in _m)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row

    tareas = conn.execute(
        "SELECT t.id, t.text, t.status, t.priority, u.name AS owner "
        "FROM tareas t LEFT JOIN users u ON u.id=t.user_id "
        f"WHERE COALESCE(t.shared,0)=1 AND t.user_id IN ({_mph}) "
        "ORDER BY t.status, t.id DESC LIMIT 30", _m).fetchall()
    notas = conn.execute(
        "SELECT n.id, n.text, n.created_at, u.name AS owner "
        "FROM notas n LEFT JOIN users u ON u.id=n.user_id "
        f"WHERE COALESCE(n.shared,0)=1 AND n.user_id IN ({_mph}) "
        "ORDER BY n.id DESC LIMIT 15", _m).fetchall()
    conn.close()

    if not tareas and not notas:
        await update.message.reply_text("👥 Nada compartido todavia.\n\nProbá: /compartir todas (comparte tus tareas pendientes)"); return

    msg = "👥 Compartido entre los dos\n"
    if tareas:
        msg += "\n✅ Tareas:\n"
        pri_icon = {"alta":"🔴","media":"🟡","baja":"🟢"}
        for t in tareas:
            check = "✓" if t["status"] == "hecha" else "○"
            owner = f" · creada por {t['owner']}" if t["owner"] else ""
            msg += f"  {check} {pri_icon.get(t['priority'],'⚪')} #{t['id']} {t['text']}{owner}\n"
    if notas:
        msg += "\n📓 Notas:\n"
        for n in notas:
            snip = n["text"][:60] + ("…" if len(n["text"]) > 60 else "")
            owner = f" · de {n['owner']}" if n["owner"] else ""
            msg += f"  #{n['id']} {snip}{owner}\n"
    msg += "\nPara dejar de compartir: /compartir off tarea <id>"
    await update.message.reply_text(msg)

async def buscar_cmd(update, context):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Usa: /buscar TEXTO"); return
    q = " ".join(context.args).strip()
    if len(q) < 2:
        await update.message.reply_text("Minimo 2 caracteres."); return
    uid = current_user_id(update)
    like = f"%{q}%"
    out = [f"🔍 «{q}»"]
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    txs = conn.execute(
        "SELECT t.id,t.type,t.amount,t.currency,t.description,t.occurred_at,a.name AS acc "
        "FROM transactions t JOIN accounts a ON a.id=t.account_id "
        "WHERE t.user_id=? AND LOWER(COALESCE(t.description,'')) LIKE LOWER(?) "
        "ORDER BY t.occurred_at DESC LIMIT 5", (uid, like)).fetchall()
    if txs:
        out.append("\n💸 Transacciones:")
        for r in txs:
            sign = "+" if r['type']=='ingreso' else "-"; emoji = "🟢" if r['type']=='ingreso' else "🔴"
            d = datetime.fromisoformat(r['occurred_at']).strftime("%d/%m")
            out.append(f"  {emoji} #{r['id']} {d} {sign}{r['amount']:,.2f} {r['currency']} · {r['description'] or ''} ({r['acc']})")
    tas = conn.execute("SELECT id,text,status FROM tareas WHERE user_id=? AND text LIKE ? ORDER BY id DESC LIMIT 5", (uid, like)).fetchall()
    if tas:
        out.append("\n✅ Tareas:")
        for r in tas:
            icon = "✓" if r['status']=='hecha' else "○"
            out.append(f"  {icon} #{r['id']} {r['text']}")
    nts = conn.execute("SELECT id,text,created_at FROM notas WHERE user_id=? AND text LIKE ? ORDER BY created_at DESC LIMIT 5", (uid, like)).fetchall()
    if nts:
        out.append("\n📓 Notas:")
        for r in nts:
            snip = r['text'][:100] + ("…" if len(r['text'])>100 else "")
            d = datetime.fromisoformat(r['created_at']).strftime("%d/%m")
            out.append(f"  #{r['id']} {d}: {snip}")
    evs = conn.execute(
        "SELECT id,title,starts_at,location FROM eventos "
        "WHERE user_id=? AND (LOWER(title) LIKE LOWER(?) OR LOWER(COALESCE(location,'')) LIKE LOWER(?) OR LOWER(COALESCE(notes,'')) LIKE LOWER(?)) "
        "ORDER BY starts_at DESC LIMIT 5", (uid, like, like, like)).fetchall()
    if evs:
        out.append("\n📅 Eventos:")
        for r in evs:
            d = datetime.fromisoformat(r['starts_at']).strftime("%d/%m %H:%M")
            loc = f" · {r['location']}" if r['location'] else ""
            out.append(f"  #{r['id']} {d} {r['title']}{loc}")
    rms = conn.execute(
        "SELECT id,text,remind_at,fired FROM recordatorios "
        "WHERE user_id=? AND LOWER(text) LIKE LOWER(?) ORDER BY remind_at DESC LIMIT 5", (uid, like)).fetchall()
    if rms:
        out.append("\n⏰ Recordatorios:")
        for r in rms:
            d = datetime.fromisoformat(r['remind_at']).strftime("%d/%m %H:%M")
            estado = "✓" if r['fired'] else "⏳"
            out.append(f"  {estado} #{r['id']} {d}: {r['text']}")
    conn.close()
    if len(out) == 1: out.append("\nSin resultados.")
    await update.message.reply_text("\n".join(out))


async def tx_cmd(update, context):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Usa: /tx N"); return
    try: tid = int(context.args[0].lstrip("#"))
    except ValueError: await update.message.reply_text("Pasame un numero."); return
    uid = current_user_id(update)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT t.*, a.name AS acc_name, a.icon AS acc_icon, c.name AS cat_name, c.icon AS cat_icon "
        "FROM transactions t JOIN accounts a ON a.id=t.account_id "
        "LEFT JOIN categories c ON c.id=t.category_id WHERE t.id=? AND t.user_id=?", (tid, uid)).fetchone()
    conn.close()
    if not row: await update.message.reply_text(f"No encontre #{tid} entre las tuyas"); return
    sign = "+" if row['type']=='ingreso' else "-"; emoji = "🟢" if row['type']=='ingreso' else "🔴"
    d = datetime.fromisoformat(row['occurred_at'])
    cat_str = f"{row['cat_icon'] or ''} {row['cat_name']}" if row['cat_name'] else "(sin categoria)"
    msg = (f"{emoji} Transaccion #{row['id']}\n\n"
           f"💵 {sign}{row['amount']:,.2f} {row['currency']}\n"
           f"📝 {row['description'] or '(sin descripcion)'}\n"
           f"📂 {row['acc_icon'] or ''} {row['acc_name']}\n"
           f"🏷️ {cat_str}\n"
           f"📅 {DIAS_ES[d.weekday()]} {d.strftime('%d/%m/%Y %H:%M')}")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Borrar", callback_data=f"txdel:{tid}")]])
    await update.message.reply_text(msg, reply_markup=kb)


async def resumen_cmd(update, context, user_id=None, shared=False):
    if not is_allowed(update): return
    uid = user_id if user_id is not None else current_user_id(update)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    now = now_local(); mes_ini = now.strftime("%Y-%m-01")
    if shared:
        # "compartido" = miembros de MI hogar (aislamiento), no global.
        _m = household_member_ids(uid); _mph = ",".join("?" for _ in _m)
        totales = conn.execute(
            f"SELECT type, currency, SUM(amount) AS t FROM transactions WHERE occurred_at>=? AND user_id IN ({_mph}) GROUP BY type, currency",
            [mes_ini] + _m).fetchall()
        por_cat = conn.execute(
            "SELECT COALESCE(c.name,'(sin categoria)') AS cat, t.currency, SUM(t.amount) AS total "
            "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            f"WHERE t.occurred_at>=? AND t.type='gasto' AND t.user_id IN ({_mph}) GROUP BY cat, t.currency ORDER BY total DESC LIMIT 10",
            [mes_ini] + _m).fetchall()
        por_acc = conn.execute(
            "SELECT a.name AS acc, t.currency, SUM(t.amount) AS total FROM transactions t "
            f"JOIN accounts a ON a.id=t.account_id WHERE t.occurred_at>=? AND t.type='gasto' AND t.user_id IN ({_mph}) "
            "GROUP BY a.name, t.currency ORDER BY total DESC", [mes_ini] + _m).fetchall()
        eventos = conn.execute(
            f"SELECT title,starts_at,location FROM eventos WHERE starts_at>=? AND user_id IN ({_mph}) ORDER BY starts_at LIMIT 5",
            [now.strftime("%Y-%m-%dT%H:%M")] + _m).fetchall()
    else:
        totales = conn.execute(
            "SELECT type, currency, SUM(amount) AS t FROM transactions WHERE occurred_at>=? AND user_id=? GROUP BY type, currency",
            (mes_ini, uid)).fetchall()
        por_cat = conn.execute(
            "SELECT COALESCE(c.name,'(sin categoria)') AS cat, t.currency, SUM(t.amount) AS total "
            "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
            "WHERE t.occurred_at>=? AND t.type='gasto' AND t.user_id=? GROUP BY cat, t.currency ORDER BY total DESC LIMIT 10",
            (mes_ini, uid)).fetchall()
        por_acc = conn.execute(
            "SELECT a.name AS acc, t.currency, SUM(t.amount) AS total FROM transactions t "
            "JOIN accounts a ON a.id=t.account_id WHERE t.occurred_at>=? AND t.type='gasto' AND t.user_id=? "
            "GROUP BY a.name, t.currency ORDER BY total DESC", (mes_ini, uid)).fetchall()
        eventos = conn.execute(
            "SELECT title,starts_at,location FROM eventos WHERE starts_at>=? AND user_id=? ORDER BY starts_at LIMIT 5",
            (now.strftime("%Y-%m-%dT%H:%M"), uid)).fetchall()
    conn.close()
    titulo_extra = " — compartido" if shared else ""
    msg = f"📊 Resumen — {MESES_ES[now.month-1]} {now.year}{titulo_extra}\n\n"
    gastos = [t for t in totales if t['type']=='gasto']
    ingresos = [t for t in totales if t['type']=='ingreso']
    if gastos:
        msg += "💸 Gastos\n"
        for g in gastos: msg += f"  {g['currency']}: {g['t']:,.2f}\n"
    if ingresos:
        msg += "💰 Ingresos\n"
        for i in ingresos: msg += f"  {i['currency']}: {i['t']:,.2f}\n"
    if not gastos and not ingresos: msg += "Sin movimientos este mes.\n"
    if por_cat:
        msg += "\n🏷️ Por categoria:\n"
        for c in por_cat: msg += f"• {c['cat']}: {c['total']:,.2f} {c['currency']}\n"
    if por_acc:
        msg += "\n💳 Por cuenta:\n"
        for a in por_acc: msg += f"• {a['acc']}: {a['total']:,.2f} {a['currency']}\n"
    # 🎯 Presupuestos + 🔁 Posibles suscripciones (solo en resumen personal)
    if not shared:
        try:
            buds = budgets_for_user(uid)
            if buds:
                msg += "\n🎯 Presupuestos\n"
                for b in sorted(buds, key=lambda x: -(x["spent_ars"] / x["limit"] if x["limit"] else 0)):
                    st = finance.budget_status(b["spent_ars"], b["limit"])
                    bar = finance.progress_bar(st["pct"])
                    icon = {"ok": "🟢", "warn": "🟡", "over": "🔴"}.get(st["level"], "🟢")
                    proj = finance.project_month_end(b["spent_ars"], now.day, _days_in_month(now))
                    msg += (f"{icon} {b['cat_name']}: {b['spent_ars']:,.0f}/{b['limit']:,.0f} "
                            f"({st['pct']:.0f}%) {bar}\n")
                    if proj > b["limit"] and st["level"] != "over":
                        msg += f"   📈 proyeccion fin de mes: {proj:,.0f} ARS (excede)\n"
        except Exception:
            log.exception("resumen presupuestos (no critico)")
        try:
            cands = recurring_candidates(uid)
            if cands:
                msg += "\n🔁 Posibles suscripciones (no agendadas)\n"
                for cc in cands[:5]:
                    msg += (f"• {cc['description']} ~{cc['amount']:,.0f} {cc['currency']} "
                            f"({cc['occurrences']}x en {cc['months']} meses)\n")
                msg += "Para agendarlas usá /suscripciones\n"
        except Exception:
            log.exception("resumen suscripciones (no critico)")
    msg += "\n📅 Proximos eventos\n"
    if eventos:
        for title,starts_at,loc in eventos:
            line = f"• {fmt_dt(starts_at)} — {title}"
            if loc: line += f" ({loc})"
            msg += line + "\n"
    else: msg += "Nada agendado.\n"
    await update.message.reply_text(msg)


async def cuentas_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    accs = list_accounts(user_id=uid)
    if not accs:
        await update.message.reply_text("Sin cuentas configuradas.\nCrea una con /addcuenta nombre [tipo] o «crear cuenta X»."); return
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    msg = "💳 Cuentas y balances\n\n"
    for a in accs:
        bals = conn.execute(
            "SELECT currency, SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS bal "
            "FROM transactions WHERE account_id=? GROUP BY currency", (a['id'],)).fetchall()
        msg += f"{a.get('icon','')} {a['name']}\n"
        if bals:
            for b in bals: msg += f"   {b['currency']}: {b['bal']:,.2f}\n"
        else: msg += "   (sin movimientos)\n"
    conn.close()
    await update.message.reply_text(msg)


async def recurrentes_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT r.*, a.name AS acc_name, c.name AS cat_name FROM recurring r "
        "JOIN accounts a ON a.id=r.account_id LEFT JOIN categories c ON c.id=r.category_id "
        "WHERE r.active=1 AND r.user_id=? ORDER BY r.next_occurrence LIMIT 15", (uid,)).fetchall()
    conn.close()
    if not rows: await update.message.reply_text("Sin recurrentes activas."); return
    msg = "🔁 Recurrentes activas\n\n"
    kb_rows = []
    for r in rows:
        sign = "💸" if r['type']=='gasto' else "💰"
        cuota_info = ""
        if r['total_installments']:
            cuota_info = f" · cuota {(r['installments_fired'] or 0)+1}/{r['total_installments']}"
        msg += f"{sign} #{r['id']} {r['description']} — {r['amount']:,.2f} {r['currency']}{cuota_info}\n"
        msg += f"   📂 {r['acc_name']}"
        if r['cat_name']: msg += f" · 🏷️ {r['cat_name']}"
        msg += f"\n   📅 Dia {r['day_of_month']} · proxima: {r['next_occurrence']}\n\n"
        kb_rows.append([
            InlineKeyboardButton(f"⏸ #{r['id']}", callback_data=f"rectoggle:{r['id']}"),
            InlineKeyboardButton(f"× #{r['id']}", callback_data=f"recdel:{r['id']}"),
        ])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb_rows))


async def movimientos_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    n = 15
    if context and getattr(context, "args", None):
        try: n = min(max(int(context.args[0]), 1), 50)
        except (ValueError, TypeError): pass
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT t.id, t.type, t.amount, t.currency, t.description, t.occurred_at, "
        "a.name AS acc, c.name AS cat FROM transactions t "
        "JOIN accounts a ON a.id=t.account_id LEFT JOIN categories c ON c.id=t.category_id "
        "WHERE t.user_id=? ORDER BY DATE(t.occurred_at) DESC, t.id DESC LIMIT ?", (uid, n)).fetchall()
    conn.close()
    if not rows: await update.message.reply_text("Sin movimientos."); return
    msg = f"📋 Ultimos {len(rows)} movimientos:\n"
    current_day = None
    for r in rows:
        d = datetime.fromisoformat(r['occurred_at'])
        day_str = f"{DIAS_ES[d.weekday()]} {d.strftime('%d/%m')}"
        if day_str != current_day:
            msg += f"\n📅 {day_str}\n"
            current_day = day_str
        emoji = "🟢" if r['type']=='ingreso' else "🔴"
        sign = "+" if r['type']=='ingreso' else "-"
        line = f"{emoji} #{r['id']} {sign}{r['amount']:,.2f} {r['currency']}"
        if r['description']: line += f" · {r['description']}"
        line += f"\n   📂 {r['acc']}"
        if r['cat']: line += f" · 🏷️ {r['cat']}"
        msg += line + "\n"
    msg += "\n/borrar N para borrar una"
    await update.message.reply_text(msg)


async def borrar_cmd(update, context):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Usa: /borrar <id>"); return
    try: tid = int(context.args[0].lstrip("#"))
    except ValueError: await update.message.reply_text("Pasame un numero."); return
    uid = current_user_id(update)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT amount,currency,description FROM transactions WHERE id=? AND user_id=?", (tid, uid)).fetchone()
    if not row:
        conn.close(); await update.message.reply_text(f"No encontre #{tid} entre tus transacciones"); return
    conn.execute("DELETE FROM transactions WHERE id=?", (tid,)); conn.commit(); conn.close()
    await update.message.reply_text(f"🗑️ #{tid} borrada: {row['amount']:,.2f} {row['currency']} {row['description'] or ''}")


async def tareas_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    _m = household_member_ids(uid); _mph = ",".join("?" for _ in _m)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id,text,priority,due_at,COALESCE(shared,0) AS sh FROM tareas WHERE status='pendiente' "
        f"AND (user_id=? OR (COALESCE(shared,0)=1 AND user_id IN ({_mph}))) "
        "ORDER BY CASE priority WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, "
        "COALESCE(due_at,'9999'), id LIMIT 30", [uid] + _m).fetchall()
    conn.close()
    if not rows: await update.message.reply_text("Sin tareas pendientes 🎉"); return
    icons = {"alta":"🔴","media":"🟡","baja":"🟢"}
    msg = "✅ Tareas pendientes\n\n"
    for tid,text,pri,due,sh in rows:
        sh_mark = " 👥" if sh else ""
        line = f"{icons.get(pri,'⚪')} #{tid}{sh_mark} {text}"
        if due: line += f" — vence {fmt_d(due)}"
        msg += line + "\n"
    kb_rows = []
    for tid,text,pri,due,sh in rows:
        kb_rows.append([
            InlineKeyboardButton(f"✓ #{tid}", callback_data=f"tdone:{tid}"),
            InlineKeyboardButton(f"× #{tid}", callback_data=f"tdel:{tid}"),
        ])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb_rows))


async def done_cmd(update, context):
    if not is_allowed(update): return
    if not context.args: await update.message.reply_text("Usa: /done <id>"); return
    try: tid = int(context.args[0].lstrip("#"))
    except ValueError: await update.message.reply_text("Pasame un numero."); return
    uid = current_user_id(update)
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT text,status FROM tareas WHERE id=? AND user_id=?", (tid, uid)).fetchone()
    if not row: conn.close(); await update.message.reply_text(f"No encontre la tarea #{tid}"); return
    if row[1] == "hecha": conn.close(); await update.message.reply_text(f"#{tid} ya estaba hecha."); return
    conn.execute("UPDATE tareas SET status='hecha', completed_at=datetime('now') WHERE id=?", (tid,))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Hecho: {row[0]}")


async def habitos_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    today = now_local().date()
    desde7 = (now_local() - timedelta(days=6)).strftime("%Y-%m-%d 00:00:00")
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name, COUNT(*) AS cnt, SUM(value) AS total, unit "
        "FROM habito_logs WHERE user_id=? AND logged_at>=? "
        "GROUP BY name, unit ORDER BY cnt DESC",
        (uid, desde7)).fetchall()
    if not rows:
        conn.close(); await update.message.reply_text("Sin habitos en ultimos 7 dias."); return
    # metas semanales (user_settings key 'habit_goal:<name>')
    goals = {}
    for g in conn.execute(
        "SELECT key, value FROM user_settings WHERE user_id=? AND key LIKE 'habit_goal:%'",
        (uid,)).fetchall():
        try: goals[g["key"].split(":", 1)[1].lower()] = int(g["value"])
        except (ValueError, TypeError): pass
    msg = "💪 Habitos — ultimos 7 dias\n\n"
    for r in rows:
        name = r["name"]
        all_dates = [x["logged_at"] for x in conn.execute(
            "SELECT logged_at FROM habito_logs WHERE user_id=? AND name=?", (uid, name)).fetchall()]
        streak = streaks.current_streak(all_dates, today)
        days_present = {x.split("T")[0].split(" ")[0] for x in all_dates}
        flags = []
        for i in range(6, -1, -1):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            flags.append(d in days_present)
        spark = streaks.sparkline(flags)
        cnt = r["cnt"]
        _, goal, pct = streaks.weekly_progress(cnt, goals.get(name.lower()))
        head = f"• {name}: {cnt}x"
        if r["total"] and r["unit"]:
            head += f" ({r['total']:g} {r['unit']})"
        if streak > 0:
            head += f" · 🔥{streak}"
        msg += head + "\n"
        meta = ""
        if goal:
            meta = f"  meta {cnt}/{goal} ({pct}%)"
        msg += f"  {spark}{meta}\n"
    conn.close()
    await update.message.reply_text(msg)


async def pendientes_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id,text,remind_at,source FROM recordatorios WHERE fired=0 AND user_id=? ORDER BY remind_at LIMIT 15",
        (uid,)).fetchall()
    conn.close()
    if not rows: await update.message.reply_text("Sin recordatorios pendientes ✨"); return
    msg = "⏰ Proximos recordatorios\n\n"
    kb_rows = []
    for r in rows:
        tag = " (evento)" if r['source']=="evento" else ""
        msg += f"• #{r['id']} {fmt_dt(r['remind_at'])} — {r['text']}{tag}\n"
        kb_rows.append([InlineKeyboardButton(f"× cancelar #{r['id']}", callback_data=f"remdel:{r['id']}")])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb_rows))


async def notas_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    _m = household_member_ids(uid); _mph = ",".join("?" for _ in _m)
    q = " ".join(context.args).strip() if (context and getattr(context,"args",None)) else None
    conn = sqlite3.connect(DB_PATH)
    if q:
        rows = conn.execute(f"SELECT id,text,created_at,COALESCE(shared,0) AS sh FROM notas WHERE (user_id=? OR (COALESCE(shared,0)=1 AND user_id IN ({_mph}))) AND text LIKE ? ORDER BY created_at DESC LIMIT 10",[uid] + _m + [f"%{q}%"]).fetchall()
        header = f"📓 Notas con «{q}»\n\n"
    else:
        rows = conn.execute(f"SELECT id,text,created_at,COALESCE(shared,0) AS sh FROM notas WHERE (user_id=? OR (COALESCE(shared,0)=1 AND user_id IN ({_mph}))) ORDER BY created_at DESC LIMIT 10", [uid] + _m).fetchall()
        header = "📓 Ultimas notas\n\n"
    conn.close()
    if not rows: await update.message.reply_text("Sin notas."); return
    msg = header
    for nid,text,created,sh in rows:
        snip = text if len(text)<200 else text[:200]+"…"
        d = datetime.fromisoformat(created).strftime("%d/%m %H:%M")
        marker = " 👥" if sh else ""
        msg += f"#{nid}{marker} ({d})\n{snip}\n\n"
    await update.message.reply_text(msg)


async def cotizacion_cmd(update, context):
    if not is_allowed(update): return
    msg = "💱 Cotizacion USD\n\n"
    for t in ["oficial","blue","mep","cripto"]:
        rate = get_dolar_rate(t)
        msg += f"{t.capitalize()}: " + (f"${rate:,.2f}" if rate else "no disponible") + "\n"
    await update.message.reply_text(msg)


def resolve_period(period):
    if not period: return None, None
    now = now_local(); today = now.date()
    p = unicodedata.normalize("NFD", str(period).lower().strip())
    p = "".join(c for c in p if unicodedata.category(c) != "Mn")
    p = p.replace(" ", "_")
    if p in ("hoy","today","este_dia"):
        s = today.strftime("%Y-%m-%d"); return s, s
    if p in ("ayer","yesterday"):
        y = (today - timedelta(days=1)).strftime("%Y-%m-%d"); return y, y
    if p in ("semana","esta_semana","ultima_semana","week","ultimos_7_dias","7_dias"):
        s = (today - timedelta(days=6)).strftime("%Y-%m-%d")
        return s, today.strftime("%Y-%m-%d")
    if p in ("semana_pasada","la_semana_pasada","last_week"):
        monday_this = today - timedelta(days=today.weekday())
        end = monday_this - timedelta(days=1)
        start = end - timedelta(days=6)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    if p in ("mes","este_mes","month","mes_actual"):
        s = today.strftime("%Y-%m-01")
        return s, today.strftime("%Y-%m-%d")
    if p in ("mes_pasado","last_month","el_mes_pasado","mes_anterior"):
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.strftime("%Y-%m-%d"), last_prev.strftime("%Y-%m-%d")
    if p in ("ano","year","este_ano","ano_actual"):
        s = today.strftime("%Y-01-01"); return s, today.strftime("%Y-%m-%d")
    if p in ("ano_pasado","last_year","el_ano_pasado"):
        y = today.year - 1; return f"{y}-01-01", f"{y}-12-31"
    if p in ("todo","all","historico","siempre"):
        return None, None
    return None, None


def _period_label(date_from, date_to, period):
    if period:
        labels = {
            "hoy":"hoy","ayer":"ayer","semana":"ultimos 7 dias","semana_pasada":"la semana pasada",
            "mes":"este mes","mes_pasado":"el mes pasado","ano":"este ano","ano_pasado":"el ano pasado","todo":"historico",
        }
        key = unicodedata.normalize("NFD", period.lower()).encode("ascii","ignore").decode().replace(" ","_")
        if key in labels: return labels[key]
    if date_from and date_to:
        return f"del {date_from} al {date_to}" if date_from != date_to else f"el {date_from}"
    if date_from: return f"desde {date_from}"
    if date_to: return f"hasta {date_to}"
    return "historico"


def resolve_scope(scope_str, asker_id):
    """Devuelve (uid|None, label). None = TODO MI HOGAR (no global). 'user:X' solo se
    permite si X pertenece al hogar del que pregunta (si no, cae a uno mismo → sin fuga)."""
    members = household_member_ids(asker_id)
    if not scope_str: return asker_id, ""
    s = str(scope_str).strip().lower()
    if s in ("mine","mio","yo","propio"): return asker_id, ""
    if s in ("ours","ambos","los_dos","los dos","shared","compartido","both","juntos"):
        return None, " · compartido"
    if s.startswith("user:"):
        u = get_user_by_name(s.split(":",1)[1].strip())
        if u and u["id"] in members: return u["id"], f" · de {u['name']}"
        return asker_id, ""
    u = get_user_by_name(s)
    if u and u["id"] in members: return u["id"], f" · de {u['name']}"
    return asker_id, ""


def build_consulta_filter(filters, asker_id):
    f = filters or {}
    where = []; params = []
    scope_uid, scope_label = resolve_scope(f.get("scope"), asker_id)
    if scope_uid is not None:
        where.append("t.user_id = ?"); params.append(scope_uid)
    else:  # "compartido" = SOLO mi hogar (no global)
        _m = household_member_ids(asker_id)
        where.append(f"t.user_id IN ({','.join('?' for _ in _m)})"); params.extend(_m)
    if f.get("keyword"):
        kw = str(f["keyword"]).strip()
        where.append(
            "(LOWER(COALESCE(t.description,'')) LIKE LOWER(?) "
            "OR EXISTS (SELECT 1 FROM categories c2 WHERE c2.id=t.category_id "
            "AND LOWER(c2.name) LIKE LOWER(?)))")
        params.append(f"%{kw}%"); params.append(f"%{kw}%")
    if f.get("category"):
        cat = get_category_by_name(f["category"])
        if cat:
            where.append("t.category_id = ?"); params.append(cat["id"])
        else:
            where.append("LOWER(COALESCE(t.description,'')) LIKE LOWER(?)")
            params.append(f"%{f['category']}%")
    if f.get("account"):
        acc = get_account_by_name(f["account"], user_id=(scope_uid if scope_uid is not None else asker_id))
        if acc:
            where.append("t.account_id = ?"); params.append(acc["id"])
    if f.get("type"):
        where.append("t.type = ?"); params.append(f["type"])
    if f.get("currency"):
        where.append("t.currency = ?"); params.append(f["currency"])
    df, dt = resolve_period(f.get("period"))
    date_from = f.get("date_from") or df
    date_to = f.get("date_to") or dt
    if date_from:
        where.append("t.occurred_at >= ?"); params.append(date_from)
    if date_to:
        where.append("t.occurred_at <= ?"); params.append(date_to + "T23:59")
    if f.get("amount_min") is not None:
        where.append("t.amount >= ?"); params.append(float(f["amount_min"]))
    if f.get("amount_max") is not None:
        where.append("t.amount <= ?"); params.append(float(f["amount_max"]))
    where_clause = " AND ".join(where) if where else "1=1"
    return where_clause, params, (date_from, date_to), scope_label, scope_uid


def _filters_label(filters):
    bits = []
    f = filters or {}
    if f.get("keyword"): bits.append(f["keyword"])
    if f.get("category"): bits.append(f["category"])
    if f.get("account"): bits.append(f["account"])
    if f.get("amount_min") is not None: bits.append(f"≥ {f['amount_min']:,.0f}")
    if f.get("amount_max") is not None: bits.append(f"≤ {f['amount_max']:,.0f}")
    return " · ".join(bits)


async def _eventos_query(update, filters, asker_id):
    f = filters or {}
    df, dt = resolve_period(f.get("period"))
    date_from = f.get("date_from") or df
    date_to = f.get("date_to") or dt
    scope_uid, scope_label = resolve_scope(f.get("scope"), asker_id)
    where = []; params = []
    if scope_uid is not None:
        where.append("user_id = ?"); params.append(scope_uid)
    else:  # "compartido" = solo mi hogar
        _m = household_member_ids(asker_id)
        where.append(f"user_id IN ({','.join('?' for _ in _m)})"); params.extend(_m)
    if date_from:
        where.append("starts_at >= ?"); params.append(date_from)
    else:
        where.append("starts_at >= ?"); params.append(now_local().strftime("%Y-%m-%dT%H:%M"))
    if date_to:
        where.append("starts_at <= ?"); params.append(date_to + "T23:59")
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"SELECT id,title,starts_at,location FROM eventos WHERE {' AND '.join(where)} "
        f"ORDER BY starts_at LIMIT 15", params).fetchall()
    conn.close()
    plabel = _period_label(date_from, date_to, f.get("period"))
    if not rows:
        await update.message.reply_text(f"📅 Sin eventos {plabel}{scope_label}."); return
    msg = f"📅 Eventos ({plabel}{scope_label})\n\n"
    for r in rows:
        line = f"• #{r['id']} {fmt_dt(r['starts_at'])} — {r['title']}"
        if r['location']: line += f" ({r['location']})"
        msg += line + "\n"
    await update.message.reply_text(msg)


async def _balance_query(update, filters, asker_id):
    f = filters or {}
    acc = get_account_by_name(f.get("account"), user_id=asker_id) if f.get("account") else None
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    if acc:
        rows = conn.execute(
            "SELECT currency, SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS bal "
            "FROM transactions WHERE account_id=? GROUP BY currency", (acc['id'],)).fetchall()
        conn.close()
        if not rows:
            await update.message.reply_text(f"{acc.get('icon','')} {acc['name']}: sin movimientos."); return
        msg = f"{acc.get('icon','')} {acc['name']}\n"
        for b in rows: msg += f"   {b['currency']}: {b['bal']:,.2f}\n"
        await update.message.reply_text(msg); return
    conn.close()
    await cuentas_cmd(update, None)


def _distinct_keyword_candidates(scope_uid, asker_id=None):
    """Tokens distintos de descripciones (del usuario o de SU HOGAR) + nombres de categorias.
    scope_uid None => miembros del hogar de asker_id (NUNCA global)."""
    cats, tokens = [], set()
    with db() as c:
        for r in c.execute("SELECT name FROM categories").fetchall():
            if r["name"]:
                cats.append(r["name"])
        if scope_uid is not None:
            rows = c.execute("SELECT DISTINCT description FROM transactions "
                             "WHERE user_id=? AND description IS NOT NULL AND description<>''",
                             (scope_uid,)).fetchall()
        else:
            _m = household_member_ids(asker_id) if asker_id else []
            rows = c.execute(
                f"SELECT DISTINCT description FROM transactions WHERE user_id IN ({','.join('?' for _ in _m)}) "
                "AND description IS NOT NULL AND description<>''", _m).fetchall() if _m else []
    for r in rows:
        for tok in str(r["description"]).split():
            tok = tok.strip(".,;:()«»\"'").lower()
            if len(tok) >= 3:
                tokens.add(tok)
    return cats + sorted(tokens)


def _maybe_fuzzy_keyword(filters, scope_uid, asker_id=None):
    """Si hay keyword, devuelve (close_match, new_filters) o (None, None)."""
    kw = (filters or {}).get("keyword")
    if not kw:
        return None, None
    cand = _distinct_keyword_candidates(scope_uid, asker_id)
    close = conversation.fuzzy_keyword(kw, cand, cutoff=0.6)
    if not close or conversation._norm(close) == conversation._norm(kw):
        return None, None
    nf = dict(filters); nf["keyword"] = close
    return close, nf


async def handle_consulta_intent(update, context, c):
    c = c or {}
    asker_id = current_user_id(update)
    # memoria de follow-ups: guardamos la consulta resuelta para patchear continuaciones
    try:
        if context is not None and getattr(context, "user_data", None) is not None:
            context.user_data["last_consulta"] = json.loads(json.dumps(c))
            context.user_data["last_consulta_ts"] = now_local().timestamp()
    except Exception:
        log.exception("no pude stashear last_consulta")
    # balance de la pareja (Fase 4) — short-circuit despues del stash de Fase 1
    if (c.get("type") if isinstance(c, dict) else None) == "balance_pareja":
        me = current_user(update)
        if not me:
            await update.message.reply_text("No estas registrado en la DB."); return
        text, _ = balance_text_for(me)
        await update.message.reply_text(text)
        return
    ctype = (c.get("type") or "").lower()
    intencion = (c.get("intencion") or "").lower() or None
    filters = c.get("filters") or {}
    if c.get("period") and "period" not in filters:
        filters = dict(filters); filters["period"] = c["period"]
    limit = c.get("limit")
    group_by = (c.get("group_by") or "").lower() or None
    order = (c.get("order") or "newest").lower()

    if ctype == "pendientes": return await pendientes_cmd(update, context)
    if ctype == "habitos":    return await habitos_cmd(update, context)
    if ctype == "notas":      return await notas_cmd(update, context)
    if ctype == "recurrentes":return await recurrentes_cmd(update, context)
    if ctype == "cotizacion": return await cotizacion_cmd(update, context)
    if ctype == "tareas":     return await tareas_cmd(update, context)
    if ctype == "eventos":    return await _eventos_query(update, filters, asker_id)
    if ctype == "balance":    return await _balance_query(update, filters, asker_id)
    if ctype == "cuentas":
        if filters.get("account"): return await _balance_query(update, filters, asker_id)
        return await cuentas_cmd(update, context)

    scope_uid, _ = resolve_scope(filters.get("scope"), asker_id)
    if ctype == "resumen" and not _filters_label(filters) and not limit and not intencion and not group_by:
        shared = scope_uid is None
        return await resumen_cmd(update, context, user_id=(None if shared else asker_id), shared=shared)

    where, params, (date_from, date_to), scope_label, scope_uid = build_consulta_filter(filters, asker_id)
    plabel = _period_label(date_from, date_to, filters.get("period"))
    flabel = _filters_label(filters)

    cmp_period = c.get("compare_period") or filters.get("compare_period")
    if cmp_period:
        # periodo A = el de la consulta; periodo B = compare_period
        where_a, params_a, (af, at), scope_label, _ = build_consulta_filter(filters, asker_id)
        fb = dict(filters); fb["period"] = cmp_period
        fb.pop("date_from", None); fb.pop("date_to", None)
        where_b, params_b, (bf, bt), _, _ = build_consulta_filter(fb, asker_id)
        sql_tpl = ("SELECT t.currency, SUM(t.amount) AS total FROM transactions t "
                   "WHERE {w} GROUP BY t.currency")
        with db() as conn:
            rows_a = conn.execute(sql_tpl.format(w=where_a), params_a).fetchall()
            rows_b = conn.execute(sql_tpl.format(w=where_b), params_b).fetchall()
        if not rows_a and not rows_b:
            await update.message.reply_text(f"Sin movimientos para comparar{scope_label}."); return
        delta = compare.period_delta(
            [{"currency": r["currency"], "total": r["total"]} for r in rows_a],
            [{"currency": r["currency"], "total": r["total"]} for r in rows_b])
        tipo_str = ("ingresos" if filters.get("type") == "ingreso"
                    else "gastos" if filters.get("type") == "gasto" else "movimientos")
        label_a = _period_label(af, at, filters.get("period"))
        label_b = _period_label(bf, bt, cmp_period)
        await update.message.reply_text(
            compare.format_comparison(label_a, label_b, delta, tipo_str) + scope_label); return

    if intencion == "ranking" or group_by in ("category","account","user"):
        gb = group_by or "category"
        if gb == "category":
            sql = (f"SELECT COALESCE(c.name,'(sin categoria)') AS grp, t.currency, "
                   f"SUM(t.amount) AS total, COUNT(*) AS n "
                   f"FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
                   f"WHERE {where} GROUP BY grp, t.currency ORDER BY total DESC LIMIT 10")
            header = f"🏆 Top categorias ({plabel}{scope_label})"
        elif gb == "user":
            sql = (f"SELECT COALESCE(u.name,'(?)') AS grp, t.currency, SUM(t.amount) AS total, COUNT(*) AS n "
                   f"FROM transactions t LEFT JOIN users u ON u.id=t.user_id "
                   f"WHERE {where} GROUP BY grp, t.currency ORDER BY total DESC")
            header = f"👥 Por persona ({plabel}{scope_label})"
        else:
            sql = (f"SELECT a.name AS grp, t.currency, SUM(t.amount) AS total, COUNT(*) AS n "
                   f"FROM transactions t JOIN accounts a ON a.id=t.account_id "
                   f"WHERE {where} GROUP BY grp, t.currency ORDER BY total DESC")
            header = f"💳 Por cuenta ({plabel}{scope_label})"
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall(); conn.close()
        if not rows:
            await update.message.reply_text(f"Sin movimientos {plabel}{scope_label}."); return
        msg = header + ("\n" + flabel + "\n\n" if flabel else "\n\n")
        for r in rows: msg += f"• {r['grp']}: {r['total']:,.2f} {r['currency']} ({r['n']} mov)\n"
        await update.message.reply_text(msg); return

    if intencion in ("total","conteo","promedio","max","min"):
        sql = (f"SELECT t.currency, SUM(t.amount) AS total, COUNT(*) AS n, "
               f"AVG(t.amount) AS prom, MAX(t.amount) AS mx, MIN(t.amount) AS mn "
               f"FROM transactions t WHERE {where} GROUP BY t.currency")
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall(); conn.close()
        if not rows or all((r["n"] or 0) == 0 for r in rows):
            close, nf = _maybe_fuzzy_keyword(filters, scope_uid, asker_id)
            if close:
                c2 = dict(c); c2["filters"] = nf
                await update.message.reply_text(f"No encontre «{filters['keyword']}», asumiendo «{close}» 🔎")
                return await handle_consulta_intent(update, context, c2)
            extra = f" en {flabel}" if flabel else ""
            await update.message.reply_text(f"Sin movimientos {plabel}{scope_label}{extra}."); return
        tipo_str = ("ingresos" if filters.get("type") == "ingreso"
                    else "gastos" if filters.get("type") == "gasto" else "movimientos")
        head = f"📊 {tipo_str.capitalize()}"
        if flabel: head += f" · {flabel}"
        head += f" ({plabel}{scope_label})"
        msg = head + "\n\n"
        for r in rows:
            cur = r['currency']
            if intencion == "promedio":
                msg += f"• Promedio: {r['prom']:,.2f} {cur} · {r['n']} mov · total {r['total']:,.2f}\n"
            elif intencion == "max":
                msg += f"• Maximo: {r['mx']:,.2f} {cur} · {r['n']} mov\n"
            elif intencion == "min":
                msg += f"• Minimo: {r['mn']:,.2f} {cur} · {r['n']} mov\n"
            elif intencion == "conteo":
                msg += f"• {r['n']} movimientos en {cur} · total {r['total']:,.2f}\n"
            else:
                msg += f"• Total: {r['total']:,.2f} {cur} · {r['n']} mov\n"
        await update.message.reply_text(msg); return

    order_by = ("t.occurred_at ASC" if order == "oldest"
                else "t.amount DESC, t.occurred_at DESC" if order == "largest"
                else "t.occurred_at DESC, t.id DESC")
    if limit:
        try: n = max(1, min(int(limit), 50))
        except Exception: n = 15
    else:
        n = 15
    if ctype == "transacciones" and not flabel and not limit and not intencion and not group_by and scope_uid == asker_id:
        return await movimientos_cmd(update, context)

    sql = (f"SELECT t.id, t.type, t.amount, t.currency, t.description, t.occurred_at, "
           f"a.name AS acc, c.name AS cat, u.name AS owner "
           f"FROM transactions t JOIN accounts a ON a.id=t.account_id "
           f"LEFT JOIN categories c ON c.id=t.category_id "
           f"LEFT JOIN users u ON u.id=t.user_id "
           f"WHERE {where} ORDER BY {order_by} LIMIT {n}")
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall(); conn.close()
    if not rows:
        close, nf = _maybe_fuzzy_keyword(filters, scope_uid, asker_id)
        if close:
            c2 = dict(c); c2["filters"] = nf
            await update.message.reply_text(f"No encontre «{filters['keyword']}», asumiendo «{close}» 🔎")
            return await handle_consulta_intent(update, context, c2)
        extra = f" en {flabel}" if flabel else ""
        await update.message.reply_text(f"No encontre movimientos {plabel}{scope_label}{extra}."); return
    title = f"📋 {len(rows)} movimiento(s)"
    if flabel: title += f" · {flabel}"
    title += f" ({plabel}{scope_label})"
    msg = title + "\n"
    current_day = None
    show_owner = scope_uid is None
    for r in rows:
        d = datetime.fromisoformat(r['occurred_at'])
        day_str = f"{DIAS_ES[d.weekday()]} {d.strftime('%d/%m')}"
        if day_str != current_day:
            msg += f"\n📅 {day_str}\n"; current_day = day_str
        emoji = "🟢" if r['type']=='ingreso' else "🔴"
        sign = "+" if r['type']=='ingreso' else "-"
        line = f"{emoji} #{r['id']} {sign}{r['amount']:,.2f} {r['currency']}"
        if r['description']: line += f" · {r['description']}"
        line += f"\n   📂 {r['acc']}"
        if r['cat']: line += f" · 🏷️ {r['cat']}"
        if show_owner and r['owner']: line += f" · 👤 {r['owner']}"
        msg += line + "\n"
    await update.message.reply_text(msg)


async def handle_move_intent(update, context, mv):
    uid = current_user_id(update)
    target_acc = get_account_by_name(mv.get('target_account'), user_id=uid) if mv.get('target_account') else None
    target_cat = get_category_by_name(mv.get('target_category')) if mv.get('target_category') else None
    if not target_acc and not target_cat:
        await update.message.reply_text("No entendi a que cuenta o categoria mover."); return
    if mv.get('target_account') and not target_acc:
        await update.message.reply_text(f"No conozco la cuenta '{mv['target_account']}' entre las tuyas."); return
    rows = query_transactions(mv.get('filters') or {}, user_id=uid)
    if not rows:
        await update.message.reply_text("No encontre transacciones que coincidan."); return
    ids = [r['id'] for r in rows]
    target_acc_id = target_acc['id'] if target_acc else None
    target_cat_id = target_cat['id'] if target_cat else None
    if len(rows) == 1:
        apply_move(ids, target_acc_id, target_cat_id)
        r = rows[0]
        sign = "-" if r['type']=='gasto' else "+"
        msg = f"✅ Movida: #{r['id']} {sign}{r['amount']:,.2f} {r['currency']} «{r['description'] or ''}»\n"
        if target_acc: msg += f"   → 📂 {target_acc['name']}"
        if target_cat: msg += f"\n   → 🏷️ {target_cat['name']}"
        await update.message.reply_text(msg); return
    op_id = make_op_id()
    PENDING_OPS[op_id] = {"kind":"move","ids":ids,"target_account_id":target_acc_id,"target_category_id":target_cat_id}
    title = f"⚠️ Voy a mover {len(rows)} transacciones"
    if target_acc: title += f" → 📂 {target_acc['name']}"
    if target_cat: title += f" / 🏷️ {target_cat['name']}"
    extra = f"\n... y {len(rows)-5} mas" if len(rows)>5 else ""
    text = title + ":\n\n" + "\n".join(preview_lines(rows,5)) + extra
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar", callback_data=f"movok:{op_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"movno:{op_id}"),
    ]])
    await update.message.reply_text(text, reply_markup=kb)


async def handle_delete_intent(update, context, dl):
    uid = current_user_id(update)
    rows = query_transactions(dl.get('filters') or {}, user_id=uid)
    if not rows:
        await update.message.reply_text("No encontre transacciones que coincidan."); return
    ids = [r['id'] for r in rows]
    if len(rows) == 1:
        apply_delete(ids)
        r = rows[0]
        sign = "-" if r['type']=='gasto' else "+"
        await update.message.reply_text(f"🗑️ Borrada: #{r['id']} {sign}{r['amount']:,.2f} {r['currency']} «{r['description'] or ''}»"); return
    op_id = make_op_id()
    PENDING_OPS[op_id] = {"kind":"delete","ids":ids}
    extra = f"\n... y {len(rows)-5} mas" if len(rows)>5 else ""
    text = f"⚠️ Voy a BORRAR {len(rows)} transacciones:\n\n" + "\n".join(preview_lines(rows,5)) + extra
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar borrado", callback_data=f"delok:{op_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"delno:{op_id}"),
    ]])
    await update.message.reply_text(text, reply_markup=kb)


async def handle_transferencia_intent(update, context, tr, raw_id):
    uid = current_user_id(update)
    from_acc = get_account_by_name(tr.get("from_account"), user_id=uid)
    to_acc = get_account_by_name(tr.get("to_account"), user_id=uid)
    if not from_acc:
        await update.message.reply_text(f"No conozco la cuenta de origen '{tr.get('from_account')}'."); return
    if not to_acc:
        await update.message.reply_text(f"No conozco la cuenta destino '{tr.get('to_account')}'."); return
    amount = tr["amount"]
    from_cur = tr.get("from_currency") or tr.get("currency","ARS")
    to_cur = tr.get("to_currency") or from_cur
    try:
        to_amount, rate = convert_amount(amount, from_cur, to_cur, tr.get("rate_type") or "blue", tr.get("exchange_rate"))
    except Exception as e:
        await update.message.reply_text(f"No pude convertir: {e}"); return
    description = tr.get("description") or "Transferencia"
    occurred_at = tr.get("occurred_at") or now_local().strftime("%Y-%m-%dT%H:%M")
    save_transaction({"type":"gasto","amount":amount,"currency":from_cur,"account":from_acc["name"],
                      "category":"Transferencia","description":f"{description} -> {to_acc['name']}",
                      "occurred_at":occurred_at}, raw_id, uid)
    save_transaction({"type":"ingreso","amount":to_amount,"currency":to_cur,"account":to_acc["name"],
                      "category":"Transferencia","description":f"{description} <- {from_acc['name']}",
                      "occurred_at":occurred_at}, raw_id, uid)
    msg = f"🔁 Transferencia\n-{amount:,.2f} {from_cur} de {from_acc['name']}\n+{to_amount:,.2f} {to_cur} a {to_acc['name']}"
    if rate and from_cur != to_cur:
        msg += f"\n💱 @ {rate:,.2f} ({tr.get('rate_type') or 'blue'})"
    await update.message.reply_text(msg)


async def handle_editar_intent(update, context, ed):
    uid = current_user_id(update)
    if not ed.get("id"):
        await update.message.reply_text("Editar que? Decime el #ID."); return
    tid = int(ed["id"])
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM transactions WHERE id=? AND user_id=?", (tid, uid)).fetchone()
    if not row:
        conn.close(); await update.message.reply_text(f"No encontre #{tid} entre las tuyas"); return
    fields = []; params = []; changes = []
    if ed.get("amount") is not None:
        fields.append("amount=?"); params.append(ed["amount"]); changes.append(f"monto={ed['amount']:,.2f}")
    if ed.get("currency"):
        fields.append("currency=?"); params.append(ed["currency"]); changes.append(f"moneda={ed['currency']}")
    if ed.get("description"):
        fields.append("description=?"); params.append(ed["description"]); changes.append(f"descripcion=«{ed['description']}»")
    if ed.get("account"):
        acc = get_account_by_name(ed["account"], user_id=uid)
        if not acc:
            conn.close(); await update.message.reply_text(f"No conozco la cuenta '{ed['account']}' entre las tuyas."); return
        fields.append("account_id=?"); params.append(acc["id"]); changes.append(f"cuenta={acc['name']}")
    if ed.get("category"):
        cat = get_category_by_name(ed["category"])
        if not cat:
            conn.close(); await update.message.reply_text(f"No conozco la categoria '{ed['category']}'."); return
        fields.append("category_id=?"); params.append(cat["id"]); changes.append(f"categoria={cat['name']}")
    if ed.get("occurred_at"):
        fields.append("occurred_at=?"); params.append(ed["occurred_at"]); changes.append(f"fecha={ed['occurred_at']}")
    if not fields:
        conn.close(); await update.message.reply_text("No me dijiste que cambiar."); return
    params.append(tid)
    conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id=?", params)
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ #{tid} actualizada\n" + "\n".join(f"   • {c}" for c in changes))


async def handle_crear_cuenta(update, context, data):
    uid = current_user_id(update)
    name = (data.get("name") or "").strip()
    if not name:
        await update.message.reply_text("Como se llama la cuenta?"); return
    existing = get_account_by_name(name, user_id=uid)
    if existing and _norm_name(existing['name']) == _norm_name(name):
        await update.message.reply_text(f"Ya tenes «{existing['name']}»."); return
    tipo = (data.get("type") or "efectivo").lower()
    if tipo not in ("efectivo","billetera","credito","banco","inversion"):
        tipo = "efectivo"
    icono = data.get("icon")
    if not icono:
        iconos = {"efectivo":"💵","billetera":"💳","credito":"🏦","banco":"🏛️","inversion":"📈"}
        icono = iconos.get(tipo, "💳")
    create_account(uid, name, type_=tipo, icon=icono)
    await update.message.reply_text(f"✅ Cuenta «{name}» ({tipo}) creada para vos.")


async def handle_editar_cuenta(update, context, data):
    uid = current_user_id(update)
    old = (data.get("old_name") or "").strip()
    new = (data.get("new_name") or "").strip()
    if not old or not new:
        await update.message.reply_text(
            "Decime el nombre actual y el nuevo. Ej: «renombrá la cuenta Mercopal a Mercado Pago»."); return
    acc = get_account_by_name(old, user_id=uid)
    if not acc:
        await update.message.reply_text(f"No encuentro una cuenta «{old}» entre las tuyas. Mirá /cuentas."); return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE accounts SET name=? WHERE id=?", (new, acc["id"]))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Renombré «{acc['name']}» a «{new}».")


async def handle_gasto_compartido_intent(update, context, data, raw_id):
    me = current_user(update)
    if not me:
        await update.message.reply_text("No estas registrado en la DB."); return
    other = the_other_user(me["id"])
    if not other:
        await update.message.reply_text(
            "Para gastos compartidos necesito 2 usuarios activos en la pareja."); return
    amount = data.get("amount")
    if not amount:
        await update.message.reply_text("Cuanto fue el gasto compartido?"); return
    currency = data.get("currency", "ARS")
    account = data.get("account") or "Efectivo"
    description = data.get("description") or "Gasto compartido"
    other_share = splits.default_share(amount, data.get("other_share"))
    occurred_at = data.get("occurred_at") or now_local().strftime("%Y-%m-%dT%H:%M")
    tx = {"type": "gasto", "amount": amount, "currency": currency,
          "account": account, "category": data.get("category"),
          "description": description, "occurred_at": occurred_at}
    try:
        tx_id = save_transaction(tx, raw_id, me["id"])
    except Exception as e:
        log.exception("Save tx (compartido) fail")
        await update.message.reply_text(f"No pude guardar el gasto 😕\n({e})"); return
    try:
        with db() as c:
            c.execute("UPDATE transactions SET is_shared=1 WHERE id=?", (tx_id,))
    except Exception:
        log.exception("marcar is_shared fallo (no critico)")
    se_id = save_shared_expense(
        payer_user_id=me["id"], other_user_id=other["id"],
        amount=amount, other_share=other_share, currency=currency,
        description=description, occurred_at=occurred_at,
        transaction_id=tx_id, raw_id=raw_id)
    sym = {"ARS": "$", "USD": "US$", "EUR": "€"}.get(currency, currency + " ")
    reply = (f"\U0001F465 Gasto compartido guardado (#{se_id})\n"
             f"\U0001F4B8 {amount:,.2f} {currency} — {description}\n"
             f"\U0001F4C2 {account}\n"
             f"→ {other['name']} te debe {sym}{other_share:,.2f}")
    text, _ = balance_text_for(me)
    reply += "\n\n" + text
    await update.message.reply_text(reply)


async def handle_saldar_intent(update, context, data):
    me = current_user(update)
    if not me:
        await update.message.reply_text("No estas registrado en la DB."); return
    other = the_other_user(me["id"])
    if not other:
        await update.message.reply_text("Necesito 2 usuarios activos para saldar."); return
    rows = unsettled_shared(me["id"], other["id"])
    summary = splits.summarize_settlement(rows, me["id"], other["id"])
    if summary["count"] == 0:
        await update.message.reply_text(
            "No hay nada pendiente con " + other["name"] + ". Estan a mano \U0001F91D"); return
    bal_text = splits.format_balance(summary["balance"], me["name"], other["name"])
    op_id = make_op_id()
    PENDING_OPS[op_id] = {"kind": "saldar", "me_id": me["id"], "other_id": other["id"]}
    text = (f"⚖️ Voy a saldar {summary['count']} gasto(s) compartido(s) "
            f"con {other['name']}:\n\n{bal_text}\n\n"
            f"Despues queda todo en cero.")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Saldar", callback_data=f"saldarok:{op_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"saldarno:{op_id}"),
    ]])
    await update.message.reply_text(text, reply_markup=kb)


async def handle_meta_ahorro_intent(update, context, data):
    uid = current_user_id(update)
    name = (data.get("name") or "").strip()
    if not name:
        await update.message.reply_text("¿Cómo se llama la meta de ahorro?"); return
    if data.get("add_amount") is not None:
        row = add_to_savings_goal(uid, name, data["add_amount"])
        if not row:
            await update.message.reply_text(
                f"No tenés una meta «{name}». Decime el objetivo: «quiero juntar X para {name}»."); return
        pct = (row["current_amount"] / row["target_amount"] * 100) if row["target_amount"] else 0
        bar = finance.progress_bar(pct)
        msg = (f"💰 Sumaste {data['add_amount']:,.0f} {row['currency']} a «{row['name']}».\n"
               f"{bar} {pct:.0f}%\n"
               f"{row['current_amount']:,.0f}/{row['target_amount']:,.0f} {row['currency']}")
        months = _months_until(row["deadline"])
        if pct < 100:
            sug = finance.suggested_monthly(row["target_amount"], row["current_amount"], months)
            msg += f"\n📅 Para llegar{'' if not row['deadline'] else ' a tiempo'}: ~{sug:,.0f} {row['currency']}/mes"
        else:
            msg += "\n🎉 ¡Meta cumplida!"
        await update.message.reply_text(msg); return
    target = data.get("target_amount")
    if not target:
        await update.message.reply_text(f"¿Cuánto querés juntar para «{name}»?"); return
    cur = data.get("currency") or "USD"
    create_savings_goal(uid, name, target, currency=cur, deadline=data.get("deadline"))
    months = _months_until(data.get("deadline"))
    sug = finance.suggested_monthly(target, 0, months)
    msg = (f"🎯 Meta «{name}» creada: {float(target):,.0f} {cur}.\n"
           f"{finance.progress_bar(0)} 0%")
    if data.get("deadline"):
        msg += f"\n📅 Objetivo: {data['deadline']} → ~{sug:,.0f} {cur}/mes"
    else:
        msg += f"\n(Sin fecha límite. «sumé X a {name}» para aportar.)"
    await update.message.reply_text(msg)


async def _lista_bought(update, context, uid, lst, data):
    """'compré la lista' -> marca todo comprado y (si hay monto) registra el gasto."""
    lid = lst["id"]
    pend = [i for i in _shopping_items(lid) if not i.get("done")]
    with db() as c:
        c.execute("UPDATE shopping_items SET done=1, done_at=datetime('now') WHERE list_id=? AND done=0", (lid,))
    amount = data.get("amount")
    if not amount:
        await update.message.reply_text(
            f"✅ Marqué {len(pend)} ítem(s) de {lst['name']} como comprados.\n"
            f"Si querés anotar el gasto, decime «gasté X en {lst['name'].lower()}» o «compré la lista, $X con MP».")
        return
    acc_name = data.get("account") or _first_account_name(uid)
    cur = (data.get("currency") or "ARS").upper()
    kind = lst.get("kind")
    cat = {"supermercado": "Comida", "verduleria": "Comida", "farmacia": "Salud"}.get(kind)
    tx = {"type": "gasto", "amount": amount, "currency": cur, "account": acc_name,
          "category": cat, "description": f"Compra {lst['name']}",
          "occurred_at": now_local().strftime("%Y-%m-%dT%H:%M")}
    try:
        tid = save_transaction(tx, None, uid)
    except Exception as e:
        log.exception("bought save_transaction")
        await update.message.reply_text(
            f"✅ Marqué {len(pend)} ítem(s) como comprados, pero no pude anotar el gasto 😕\n({e})")
        return
    sym = {"ARS": "$", "USD": "US$", "EUR": "€"}.get(cur, cur + " ")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Borrar gasto", callback_data=f"txdel:{tid}")]])
    await update.message.reply_text(
        f"🛒 Listo. Marqué {len(pend)} ítem(s) de {lst['name']} como comprados y anoté el gasto:\n"
        f"💸 {sym}{amount:,.2f} en {acc_name}" + (f" · {cat}" if cat else ""),
        reply_markup=kb)


async def _lista_save_template(update, uid, list_name, tname):
    """Guarda los items (pendientes+comprados, sin estado) de una lista como plantilla."""
    src = _resolve_list(list_name, uid, create=False)
    if not src:
        ref = f"«{list_name}»" if list_name else "por defecto"
        await update.message.reply_text(f"No encuentro la lista {ref} para guardar como plantilla.")
        return
    name = (tname or src["name"]).strip().title()
    with db() as c:
        items = [dict(i) for i in c.execute(
            "SELECT text, qty, unit, category, note FROM shopping_items WHERE list_id=?",
            (src["id"],)).fetchall()]
    if not items:
        await update.message.reply_text(f"La lista {src['name']} está vacía, no hay nada para guardar como plantilla.")
        return
    tpl = _find_template(name, uid)
    with db() as c:
        if tpl:
            tpl_id = tpl["id"]
            c.execute("DELETE FROM shopping_items WHERE list_id=?", (tpl_id,))
        else:
            icon, kind = _guess_list_meta(_norm_name(name))
            c.execute("INSERT INTO lists (name, kind, icon, owner_user_id, shared, is_template) VALUES (?,?,?,?,1,1)",
                      (name, kind, icon, uid))
            tpl_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        for it in items:
            c.execute("INSERT INTO shopping_items (user_id, added_by, shared, list_id, text, qty, unit, category, note, done) "
                      "VALUES (?,?,1,?,?,?,?,?,?,0)",
                      (uid, uid, tpl_id, it["text"], it["qty"], it["unit"], it["category"], it.get("note")))
    verb = "Actualicé" if tpl else "Guardé"
    await update.message.reply_text(
        f"📋 {verb} la plantilla «{name}» con {len(items)} ítem(s).\nUsala con «armá la lista de {name.lower()}».")


async def _lista_use_template(update, context, uid, tname, target_name):
    """Instancia una plantilla copiando sus items (done=0) en la lista destino."""
    if not tname:
        await update.message.reply_text("¿Qué plantilla uso? Ej: «armá la lista de compras semanales»."); return
    tpl = _find_template(tname, uid)
    if not tpl:
        await update.message.reply_text(
            f"No tengo una plantilla «{tname}». Guardá una con «guardá esta lista como plantilla {tname}».")
        return
    target = _resolve_list(target_name, uid, create=True)
    if not target:
        await update.message.reply_text("No pude resolver la lista destino."); return
    with db() as c:
        items = [dict(i) for i in c.execute(
            "SELECT text, qty, unit, category, note FROM shopping_items WHERE list_id=?",
            (tpl["id"],)).fetchall()]
        for it in items:
            c.execute("INSERT INTO shopping_items (user_id, added_by, shared, list_id, text, qty, unit, category, note, done) "
                      "VALUES (?,?,1,?,?,?,?,?,?,0)",
                      (uid, uid, target["id"], it["text"], it["qty"], it["unit"], it["category"], it["note"]))
    text, kb = _render_shopping(target["id"], target)
    await update.message.reply_text(
        f"📋 Armé «{target['name']}» con {len(items)} ítem(s) de la plantilla «{tpl['name']}».\n\n{text}",
        reply_markup=kb)


async def handle_lista_compra_intent(update, context, data):
    uid = current_user_id(update)
    action = (data.get("action") or "show").lower()
    raw_item = (data.get("item") or "").strip()
    list_name = (data.get("list") or "").strip()

    if action == "save_template":
        await _lista_save_template(update, uid, list_name, raw_item); return
    if action == "use_template":
        await _lista_use_template(update, context, uid, raw_item, list_name); return

    lst = _resolve_list(list_name, uid, create=(action == "add"))
    if not lst:
        if list_name:
            await update.message.reply_text(
                f"No tengo una lista «{list_name}». Deci «agregá X a {list_name}» y la creo.")
        else:
            await update.message.reply_text("No hay ninguna lista todavia. Probá «agregá leche a la lista».")
        return
    lid = lst["id"]
    icon = lst.get("icon") or "🛒"

    # fecha objetivo / recurrencia opcional -> guardar en la metadata de la lista
    td = (data.get("target_date") or "").strip() or None
    rec = (data.get("recurrence") or "").strip().lower() or None
    if rec not in (None, "daily", "weekly", "monthly"):
        rec = None
    if td or rec:
        sets, vals = [], []
        if td:
            sets.append("target_date=?"); vals.append(td); lst["target_date"] = td
        if rec:
            sets.append("recurrence=?"); vals.append(rec); lst["recurrence"] = rec
        vals.append(lid)
        with db() as c:
            c.execute(f"UPDATE lists SET {', '.join(sets)} WHERE id=?", vals)

    if action == "add":
        if not raw_item:
            await update.message.reply_text("Que agrego a la lista?"); return
        p = shopping.parse_item(raw_item)
        cat = shopping.aisle(p["text"])
        with db() as c:
            c.execute(
                "INSERT INTO shopping_items (user_id, added_by, shared, list_id, text, qty, unit, category, done) "
                "VALUES (?,?,1,?,?,?,?,?,0)",
                (uid, uid, lid, p["text"], p["qty"], p["unit"], cat))
        label = shopping._fmt_qty(p)
        sub = _list_subtitle(lst)
        extra = f" ({sub})" if sub else ""
        await update.message.reply_text(f"{icon} Agregué «{label}» a {lst['name']}{extra}.")
        return

    if action in ("remove", "check", "uncheck"):
        items = _shopping_items(lid)
        hit = shopping.match_item(items, raw_item)
        if not hit:
            await update.message.reply_text(f"No encontré «{raw_item}» en {lst['name']}."); return
        if action == "uncheck":
            with db() as c:
                c.execute("UPDATE shopping_items SET done=0, done_at=NULL WHERE id=?", (hit["id"],))
            await update.message.reply_text(f"↩️ «{hit['text']}» vuelve a {lst['name']}.")
        else:
            with db() as c:
                c.execute("UPDATE shopping_items SET done=1, done_at=datetime('now') WHERE id=?", (hit["id"],))
            await update.message.reply_text(f"✅ «{hit['text']}» tachado de {lst['name']}.")
        return

    if action == "clear":
        with db() as c:
            c.execute("DELETE FROM shopping_items WHERE list_id=?", (lid,))
        await update.message.reply_text(f"🧹 Vacié {lst['name']}.")
        return

    if action == "bought":
        await _lista_bought(update, context, uid, lst, data); return

    if action == "remind":
        remind_at = (data.get("remind_at") or "").strip()
        if not remind_at:
            await update.message.reply_text(f"¿Para cuándo te recuerdo «{lst['name']}»?"); return
        txt = f"Comprar: {lst['name']}"
        rid = save_recordatorio(txt, remind_at, uid, source="lista", list_id=lid)
        ok = schedule_reminder(context.application.job_queue, rid, txt, remind_at, update.effective_user.id)
        if ok:
            await update.message.reply_text(
                f"⏰ Te recuerdo la lista «{lst['name']}» el {fmt_dt(remind_at)} — con los ítems para tildar.")
        else:
            await update.message.reply_text("⚠️ Esa fecha ya pasó.")
        return

    text, kb = _render_shopping(lid, lst)
    await update.message.reply_text(text, reply_markup=kb)


async def handle_alerta_dolar_intent(update, context, data):
    uid = current_user_id(update)
    rt = (data.get("rate_type") or "blue").lower()
    if rt not in ("oficial", "blue", "mep", "cripto", "takenos"):
        rt = "blue"
    direction = (data.get("direction") or "").lower()
    if direction not in ("above", "below"):
        await update.message.reply_text("Decime si es cuando SUBE (above) o BAJA (below)."); return
    try:
        threshold = float(data.get("threshold"))
    except (TypeError, ValueError):
        await update.message.reply_text("No entendi el valor del umbral."); return
    with db() as c:
        c.execute("INSERT INTO fx_alerts (user_id, rate_type, direction, threshold) "
                  "VALUES (?,?,?,?)", (uid, rt, direction, threshold))
    verbo = "supere" if direction == "above" else "baje de"
    await update.message.reply_text(f"🔔 Listo. Te aviso cuando el dolar {rt} {verbo} ${threshold:,.2f}.")


async def handle_set_takenos_rate_intent(update, context, data):
    uid = current_user_id(update)
    try:
        value = float(data.get("value"))
    except (TypeError, ValueError):
        await update.message.reply_text("No entendi el valor del dolar Takenos."); return
    with db() as c:
        c.execute("INSERT INTO user_settings (user_id, key, value) VALUES (?,?,?) "
                  "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
                  (uid, fx.TAKENOS_RATE_KEY, str(value)))
    await update.message.reply_text(f"💱 Anotado: dolar takenos = ${value:,.2f}. "
                                    f"Lo uso para valuar tu ahorro en USD.")


async def handle_dolar_intent(update, context, data):
    await dolar_cmd(update, context)


async def handle_afford_intent(update, context, data):
    data = data or {}
    uid = current_user_id(update)
    amount = data.get("afford_amount")
    if not amount:
        await update.message.reply_text("¿Cuánto querés gastar? Ej: «¿puedo permitirme 50000 en salir?»"); return
    currency = (data.get("currency") or "ARS").upper()
    cat_name = data.get("afford_category")
    balances = {}
    with db() as conn:
        for r in conn.execute(
                "SELECT currency, SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS bal "
                "FROM transactions WHERE user_id=? GROUP BY currency", (uid,)).fetchall():
            balances[r["currency"]] = float(r["bal"] or 0)
        budget_remaining = None
        if cat_name:
            cat = get_category_by_name(cat_name)
            if cat:
                try:
                    brow = conn.execute(
                        "SELECT amount FROM budgets WHERE category_id=? AND (user_id=? OR user_id IS NULL) "
                        "ORDER BY user_id DESC LIMIT 1", (cat["id"], uid)).fetchone()
                except Exception:
                    brow = None
                if brow:
                    mes_ini = now_local().strftime("%Y-%m-01")
                    spent = conn.execute(
                        "SELECT COALESCE(SUM(amount),0) AS s FROM transactions "
                        "WHERE user_id=? AND category_id=? AND type='gasto' AND occurred_at>=?",
                        (uid, cat["id"], mes_ini)).fetchone()["s"]
                    budget_remaining = float(brow["amount"]) - float(spent)
    v = affordability.afford_verdict(
        amount, currency, balances, budget_remaining,
        value_in_ars=lambda a, cur: fx.value_in_ars(
            a, cur, get_dolar_rate, rate_type="blue", takenos_manual=_takenos_manual()))
    icon = "✅ Sí, podés" if v["affordable"] else "⛔ No te alcanza"
    msg = (f"{icon}\n"
           f"💰 Costo: {v['cost_ars']:,.0f} ARS\n"
           f"🏦 Disponible: {v['balance_ars']:,.0f} ARS\n"
           f"📉 Quedarías con: {v['leftover_ars']:,.0f} ARS")
    if v["budget_ok"] is False:
        msg += f"\n⚠️ Te pasás del presupuesto de «{cat_name}» por {v['budget_overrun']:,.0f} ARS"
    elif v["budget_ok"] is True:
        msg += f"\n👍 Dentro del presupuesto de «{cat_name}»"
    await update.message.reply_text(msg)


async def process_text(update, context, text, raw_id):
    user = current_user(update)
    if not user:
        await update.message.reply_text("No estas registrado en la DB."); return
    # ---- controles de costo (tope global diario + quota free). Fail-open. ----
    _blocked = cost_gate(user["id"])
    if _blocked:
        await update.message.reply_text(_blocked); return
    # ---- memoria de follow-ups: "¿y de Lisa?", "y la semana pasada" ----
    prev = None
    if context is not None and getattr(context, "user_data", None) is not None:
        last = context.user_data.get("last_consulta")
        last_ts = context.user_data.get("last_consulta_ts") or 0
        fresh = (now_local().timestamp() - last_ts) < 600  # 10 min
        if last and fresh and conversation.is_followup(text):
            patched = conversation.merge_followup(last, text)
            if patched is not None:
                try:
                    await process_action(update, context,
                                         {"intent": "consulta", "consulta": patched}, raw_id)
                    return
                except Exception:
                    log.exception("follow-up directo fallo, caigo al parser")
            prev = last  # damos contexto al LLM aunque no hayamos podido patchear
    try:
        acciones = parse_intent(text, user["id"], user["name"], prev_consulta=prev)
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        log.exception("Error de API parseando intent")
        await update.message.reply_text("El servicio esta lento o caido un momento 🔌\nProbá de nuevo en unos segundos."); return
    except Exception:
        log.exception("Error parseando intent")
        await update.message.reply_text("No pude entender eso 😕\nProbá reformularlo. /start para ejemplos."); return
    if not acciones:
        await update.message.reply_text("No estoy seguro de que hacer con eso. /start para ejemplos."); return
    if len(acciones) > 1:
        await update.message.reply_text(f"📦 Entendi {len(acciones)} acciones:")
    for parsed in acciones:
        try:
            await process_action(update, context, parsed, raw_id)
        except Exception:
            log.exception("Error en accion %s", parsed.get("intent"))
            await update.message.reply_text(f"✗ No pude completar la acción «{parsed.get('intent')}». Probá de nuevo.")


async def process_action(update, context, parsed, raw_id):
    intent = parsed.get("intent")
    uid = current_user_id(update)

    if intent == "transaccion" and parsed.get("transaccion"):
        txs = parsed["transaccion"]
        if not isinstance(txs, list): txs = [txs]
        for tx in txs:
            try: tid = save_transaction(tx, raw_id, uid)
            except Exception as e:
                log.exception("Save tx fail")
                await update.message.reply_text(f"No pude guardar la transaccion 😕\n({e})"); continue
            sign = "💸" if tx.get('type','gasto')=='gasto' else "💰"
            reply = f"{sign} {tx['amount']:,.2f} {tx.get('currency','ARS')}"
            if tx.get('description'): reply += f" — {tx['description']}"
            reply += f"\n📂 {tx['account']}"
            if tx.get('category'): reply += f" · 🏷️ {tx['category']}"
            # --- inteligencia post-guardado (no debe romper el happy path) ---
            try:
                cat = get_category_by_name(tx.get("category"))
                if cat and tx.get("type", "gasto") == "gasto":
                    upsert_category_learning(uid, tx.get("description"), cat["id"])
                    try:
                        amt_ars = convert_fx(tx["amount"], tx.get("currency", "ARS"), "ARS")
                    except Exception:
                        amt_ars = float(tx["amount"]) if tx.get("currency", "ARS") == "ARS" else None
                    hist = category_history_amounts(uid, cat["id"], exclude_tx_id=tid)
                    if amt_ars is not None and finance.is_anomaly(amt_ars, hist):
                        prom = sum(hist) / len(hist) if hist else 0
                        reply += (f"\n\n👀 Ojo: este gasto en «{cat['name']}» es bastante mas alto "
                                  f"que tu promedio (~{prom:,.0f} ARS). Todo bien?")
                    for b in budgets_for_user(uid):
                        if b["category_id"] != cat["id"]:
                            continue
                        st = finance.budget_status(b["spent_ars"], b["limit"])
                        bar = finance.progress_bar(st["pct"])
                        if st["level"] == "over":
                            reply += (f"\n\n🚨 Presupuesto de «{cat['name']}» SUPERADO: "
                                      f"{b['spent_ars']:,.0f}/{b['limit']:,.0f} ARS ({st['pct']:.0f}%) {bar}")
                        elif st["level"] == "warn":
                            reply += (f"\n\n⚠️ Vas al {st['pct']:.0f}% del presupuesto de «{cat['name']}» "
                                      f"({b['spent_ars']:,.0f}/{b['limit']:,.0f} ARS) {bar}")
            except Exception:
                log.exception("intel post-tx fallo (no critico)")
            await update.message.reply_text(reply)

    elif intent == "recurrente" and parsed.get("recurrente"):
        r = parsed["recurrente"]
        if not r.get("next_occurrence"): r["next_occurrence"] = now_local().strftime("%Y-%m-%d")
        if not r.get("description"): r["description"] = "recurrente"
        try: save_recurring(r, raw_id, uid)
        except Exception as e:
            log.exception("Save rec fail")
            await update.message.reply_text(f"No pude agendar la recurrente 😕\n({e})"); return
        sign = "💸" if r.get('type','gasto')=='gasto' else "💰"
        cuota_extra = f" · {r.get('total_installments')} cuotas" if r.get('total_installments') else ""
        reply = (f"🔁 Recurrente agendada{cuota_extra}\n"
                 f"{sign} {r['amount']:,.2f} {r.get('currency','ARS')} — {r['description']}\n"
                 f"📂 {r['account']}\n"
                 f"📅 Cada mes el dia {r.get('day_of_month')} · proxima: {r['next_occurrence']}")
        await update.message.reply_text(reply)

    elif intent == "transferencia" and parsed.get("transferencia"):
        await handle_transferencia_intent(update, context, parsed["transferencia"], raw_id)

    elif intent == "editar" and parsed.get("editar"):
        await handle_editar_intent(update, context, parsed["editar"])

    elif intent == "mover" and parsed.get("mover"):
        await handle_move_intent(update, context, parsed["mover"])

    elif intent == "eliminar" and parsed.get("eliminar"):
        await handle_delete_intent(update, context, parsed["eliminar"])

    elif intent == "crear_cuenta" and parsed.get("crear_cuenta"):
        await handle_crear_cuenta(update, context, parsed["crear_cuenta"])
    elif intent == "editar_cuenta" and parsed.get("editar_cuenta"):
        await handle_editar_cuenta(update, context, parsed["editar_cuenta"])

    elif intent == "evento" and parsed.get("evento"):
        e = parsed["evento"]; eid = save_evento(e, raw_id, uid)
        es_turno = e.get("kind") == "turno"
        reply = f"{'🩺 Turno' if es_turno else '📅'} {e['title']} — {fmt_dt(e['starts_at'])}"
        if e.get("location"): reply += f"\n📍 {e['location']}"
        try:
            start_dt = parse_local(e["starts_at"])
            offsets = e.get("reminder_offsets") or ([120, 30] if es_turno else [EVENT_REMINDER_MIN])
            offsets = sorted({int(o) for o in offsets if int(o) > 0}, reverse=True)
            avisados = []
            for off in offsets:
                remind_dt = start_dt - timedelta(minutes=off)
                if remind_dt > now_local():
                    rstr = remind_dt.strftime("%Y-%m-%dT%H:%M")
                    txt = e['title']
                    rid = save_recordatorio(txt, rstr, uid, source="evento", raw_id=raw_id, event_id=eid)
                    schedule_reminder(context.application.job_queue, rid, txt, rstr, update.effective_user.id)
                    avisados.append(off)
            if avisados:
                reply += "\n🔔 Te aviso " + ", ".join(f"{o}min" for o in avisados) + " antes."
        except Exception: log.exception("Reminder fail")
        if es_turno:
            reply += "\n📎 Mandame la foto de la orden con epígrafe «orden» y la guardo."
        await update.message.reply_text(reply)

    elif intent == "recordatorio" and parsed.get("recordatorio"):
        r = parsed["recordatorio"]
        rid = save_recordatorio(r["text"], r["remind_at"], uid, source="manual", raw_id=raw_id)
        rec = r.get("recurrence")
        if rec in ("daily", "weekly", "monthly"):
            with db() as c:
                c.execute("UPDATE recordatorios SET recurrence=? WHERE id=?", (rec, rid))
        ok = schedule_reminder(context.application.job_queue, rid, r["text"], r["remind_at"], update.effective_user.id)
        sufijo = {"daily": " · se repite a diario", "weekly": " · se repite semanal", "monthly": " · se repite mensual"}.get(rec, "")
        if ok:
            await update.message.reply_text(f"⏰ Te recuerdo: «{r['text']}»\n📅 {fmt_dt(r['remind_at'])}{sufijo}")
            if _wa_only(update):
                await _send_wa_reminder_notice(update)
        else:
            await update.message.reply_text("⚠️ Esa fecha ya paso.")

    elif intent == "tarea" and parsed.get("tarea"):
        t = parsed["tarea"]; tid = save_tarea(t, raw_id, uid)
        icon = {"alta":"🔴","media":"🟡","baja":"🟢"}.get(t.get("priority","media"),"🟡")
        reply = f"{icon} Tarea #{tid}: {t['text']}"
        if t.get("due_at"): reply += f"\n📅 vence {fmt_d(t['due_at'])}"
        reply += f"\n(/done {tid} cuando este hecha)"
        await update.message.reply_text(reply)

    elif intent == "habito" and parsed.get("habito"):
        h = parsed["habito"]; save_habito(h, raw_id, uid)
        bits = [f"💪 {h['name']}"]
        if h.get("value") and h.get("unit"): bits.append(f"{h['value']:g} {h['unit']}")
        await update.message.reply_text(" — ".join(bits) + " ✓")

    elif intent == "nota" and parsed.get("nota"):
        n = parsed["nota"]; nid = save_nota(n, raw_id, uid)
        await update.message.reply_text(f"📓 Nota #{nid} guardada.")

    elif intent == "gasto_compartido" and parsed.get("gasto_compartido"):
        await handle_gasto_compartido_intent(update, context, parsed.get("gasto_compartido") or {}, raw_id)

    elif intent == "saldar":
        await handle_saldar_intent(update, context, parsed.get("saldar") or {})

    elif intent == "meta_ahorro" and parsed.get("meta_ahorro"):
        await handle_meta_ahorro_intent(update, context, parsed["meta_ahorro"])

    elif intent == "lista_compra" and parsed.get("lista_compra"):
        await handle_lista_compra_intent(update, context, parsed["lista_compra"])

    elif intent == "alerta_dolar" and parsed.get("alerta_dolar") is not None:
        await handle_alerta_dolar_intent(update, context, parsed["alerta_dolar"])

    elif intent == "set_takenos_rate" and parsed.get("set_takenos_rate") is not None:
        await handle_set_takenos_rate_intent(update, context, parsed["set_takenos_rate"])

    elif intent == "dolar":
        await handle_dolar_intent(update, context, parsed.get("dolar") or {})

    elif intent == "afford" and parsed.get("afford"):
        await handle_afford_intent(update, context, parsed["afford"])

    elif intent == "precio" and parsed.get("precio"):
        await handle_precio_intent(update, context, parsed["precio"])

    elif intent == "consulta":
        await handle_consulta_intent(update, context, parsed.get("consulta") or {})

    else:
        data = parsed.get("desconocido") or {}
        aclaracion = data.get("aclaracion") if isinstance(data, dict) else None
        await update.message.reply_text(aclaracion or
            "No estoy seguro. Si era un gasto, mencioná la cuenta (ej. «pagué 1000 coca cola con MP»). /start para ejemplos.")


async def handle_text(update, context):
    if not is_allowed(update):
        await send_register_prompt(update); return
    user = update.effective_user; text = update.message.text
    raw_id = save_raw(user.id, user.username, "text", text)
    await process_text(update, context, text, raw_id)


async def handle_voice(update, context):
    if not is_allowed(update):
        await send_register_prompt(update); return
    voice = update.message.voice
    notice = await update.message.reply_text("🎙️ Transcribiendo...")
    ogg_path = VOICE_DIR / f"{voice.file_id}.ogg"
    try:
        file = await context.bot.get_file(voice.file_id)
        await file.download_to_drive(ogg_path)
        segments, _ = get_whisper().transcribe(str(ogg_path), language="es", vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
    except Exception as e:
        log.exception("Voice error"); await notice.edit_text("No pude transcribir el audio 😕 Probá de nuevo."); return
    finally:
        try: ogg_path.unlink()
        except Exception: pass
    if not text: await notice.edit_text("No te entendi en el audio."); return
    await notice.edit_text(f"📝 «{text}»")
    user = update.effective_user
    raw_id = save_raw(user.id, user.username, "voice", text)
    await process_text(update, context, text, raw_id)


async def handle_photo(update, context):
    if not is_allowed(update):
        await send_register_prompt(update); return
    user_db = current_user(update)
    if user_db:
        _blocked = cost_gate(user_db["id"])
        if _blocked:
            await update.message.reply_text(_blocked); return
    photo = update.message.photo[-1]
    caption = (update.message.caption or "").strip()
    notice = await update.message.reply_text("📸 Analizando imagen...")
    img_path = PHOTO_DIR / f"{photo.file_id}.jpg"
    try:
        file = await context.bot.get_file(photo.file_id)
        await file.download_to_drive(img_path)
        with open(img_path, "rb") as f: image_bytes = f.read()
        parsed = parse_photo(image_bytes, caption,
                             user_id=user_db["id"] if user_db else None,
                             user_name=user_db["name"] if user_db else None)
    except Exception as e:
        log.exception("Photo error"); await notice.edit_text(f"Fallo el analisis 😕\n({e})"); return
    finally:
        try: img_path.unlink()
        except Exception: pass

    user = update.effective_user
    raw_id = save_raw(user.id, user.username, "photo",
                      json.dumps({"caption":caption,"parsed":parsed}, ensure_ascii=False))

    # Normalizar cuotas_detectadas a lista
    cds = parsed.get("cuotas_detectadas") if isinstance(parsed, dict) else None
    if isinstance(cds, dict): cds = [cds]
    if not isinstance(cds, list): cds = []
    cds = [c for c in cds if c and c.get("amount") and int(c.get("cuotas_total", 0) or 0) >= 2]

    txs = parsed.get("transacciones", []) if isinstance(parsed, dict) else []
    txs = [t for t in txs if t and t.get("amount")]

    if not cds and not txs:
        await notice.edit_text("No identifique transacciones en la imagen."); return

    # ─── Caso A: cuotas detectadas ────────────────────────────────────────
    if cds:
        try: await notice.delete()
        except Exception: pass

        header = (f"📸 Detecté {len(cds)} compra(s) en cuotas en la imagen.\n"
                  f"Te pregunto una por una qué hacer con cada una.") if len(cds) > 1 else \
                 "📸 Detecté una compra en cuotas en la imagen."
        await update.message.reply_text(header)

        for i, cd in enumerate(cds, 1):
            amt = float(cd["amount"])
            n = int(cd["cuotas_total"])
            cuota_actual = max(1, int(cd.get("cuota_actual", 1) or 1))
            cur = cd.get("currency","ARS")
            desc = (cd.get("description") or "Compra en cuotas")[:80]
            acc = cd.get("account") or ""
            cat = cd.get("category") or "Otros"
            occ = cd.get("occurred_at") or now_local().strftime("%Y-%m-%dT12:00")

            op_id = make_op_id()
            PENDING_OPS[op_id] = {
                "kind": "photo_cuota",
                "amount": amt, "cuotas": n, "cuota_actual": cuota_actual,
                "currency": cur,
                "description": desc, "account": acc, "category": cat,
                "occurred_at": occ, "raw_id": raw_id,
                "user_id": user_db["id"] if user_db else None,
                "chat_id": user.id,
            }

            per = amt / n
            total = amt * n
            tag = f"[{i}/{len(cds)}] " if len(cds) > 1 else ""
            anterior = " · es una cuota ya en curso" if cuota_actual > 1 else ""
            msg = (f"{tag}💳 {acc or '(cuenta no detectada — confirmá despues)'}\n"
                   f"📝 {desc}\n"
                   f"🧾 cuota {cuota_actual}/{n}{anterior}\n"
                   f"💵 ${amt:,.2f} {cur}\n\n"
                   f"¿Ese monto es el <b>TOTAL</b> o el de <b>CADA cuota</b>?\n"
                   f"   • Si total → cada cuota ≈ <b>${per:,.2f}</b>\n"
                   f"   • Si cada cuota → total ≈ <b>${total:,.2f}</b>")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Total ${amt:,.0f} ÷ {n}", callback_data=f"phct:total:{op_id}"),
                 InlineKeyboardButton(f"Cada cuota × {n}", callback_data=f"phct:cuota:{op_id}")],
                [InlineKeyboardButton("⏭ Saltar (ya esta cargada)", callback_data=f"phct:skip:{op_id}"),
                 InlineKeyboardButton("❌ Cancelar", callback_data=f"phct:cancel:{op_id}")],
            ])
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)

    # ─── Caso B: transacciones normales (no en cuotas) ────────────────────
    if txs:
        if cds:
            await update.message.reply_text(
                f"Y además detecté {len(txs)} transacción(es) sin cuotas. Las cargo abajo:")
        saved = []
        for tx in txs:
            try:
                save_transaction(tx, raw_id, user_db["id"] if user_db else None)
                saved.append(tx)
            except Exception: log.exception("Error guardando tx de foto")
        if not saved:
            if not cds:
                await notice.edit_text("Detecte transacciones pero no pude guardarlas.")
            return
        if len(saved) == 1 and not cds:
            tx = saved[0]
            sign = "💸" if tx.get('type','gasto')=='gasto' else "💰"
            m = f"{sign} {tx['amount']:,.2f} {tx.get('currency','ARS')}"
            if tx.get('description'): m += f" — {tx['description']}"
            m += f"\n📂 {tx['account']}"
            if tx.get('category'): m += f" · 🏷️ {tx['category']}"
            await notice.edit_text(m)
        else:
            m = f"📸 {len(saved)} transacciones cargadas:\n\n"
            for tx in saved:
                sign = "-" if tx.get('type','gasto')=='gasto' else "+"
                m += f"{sign}{tx['amount']:,.2f} {tx.get('currency','ARS')} — {tx.get('description','')}\n   📂 {tx['account']}\n"
            if cds:
                await update.message.reply_text(m)
            else:
                await notice.edit_text(m)
    else:
        try: await notice.delete()
        except Exception: pass

async def reminder_watchdog(context):
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        nowstr = now_local().strftime("%Y-%m-%dT%H:%M")
        rows = conn.execute(
            "SELECT r.id, r.text, r.source, r.remind_at, r.recurrence, r.user_id, r.list_id, "
            "u.telegram_id AS owner_tg, u.telegram_id AS telegram_id "
            "FROM recordatorios r LEFT JOIN users u ON u.id=r.user_id "
            "WHERE r.fired=0 AND REPLACE(r.remind_at,' ','T') <= ? ORDER BY r.remind_at LIMIT 10",
            (nowstr,)).fetchall()
        for r in rows:
            conn.execute("UPDATE recordatorios SET fired=1 WHERE id=?", (r['id'],))
            conn.commit()
            extra = " (desde la web)" if r['source'] == "web" else ""
            chat_id = r['owner_tg'] or (ALLOWED_USER_IDS[0] if ALLOWED_USER_IDS else None)
            if chat_id:
                body, kb = f"⏰ {r['text']}{extra}", None
                if r['list_id']:
                    try:
                        ltext, kb = _render_shopping(r['list_id'])
                        body = f"⏰ {r['text']}{extra}\n\n{ltext}"
                    except Exception:
                        log.exception("render lista en watchdog %s", r['id'])
                await context.bot.send_message(chat_id=chat_id, text=body, reply_markup=kb)
            try:
                _reemit_recurring_reminder(context.application, r)
            except Exception:
                log.exception("reemit reminder %s", r['id'])
        conn.close()
    except Exception:
        log.exception("watchdog")


# max_uses acota cuántas búsquedas hace Claude por consulta (control de costo:
# cada búsqueda re-ingesta resultados y dispara los tokens de entrada).
PRICE_TOOL = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}]

def _price_search(query, user_id=None):
    """Compara precios online via web search de Claude. Sync -> correr con asyncio.to_thread."""
    msgs = [{"role": "user", "content":
        f"Buscá en la web precios actuales en PESOS ARGENTINOS de: {query}. "
        f"Compará las tiendas argentinas relevantes para ese producto (supermercados como COTO, "
        f"Carrefour/Mas Online, Dia, Jumbo, Atomo; o Mercado Libre/tiendas para electro). "
        f"Devolve una linea por tienda con '<tienda>: $<precio>' y al final marcá la mas barata. "
        f"Se conciso, SIN tablas markdown. Aclará en una linea que son precios de referencia."}]
    r = None
    # Haiku (más barato) + máx 3 vueltas de pause_turn; el costo se atribuye al usuario.
    for _ in range(3):
        r = anthropic_client.messages.create(model=MODEL, max_tokens=1024, tools=PRICE_TOOL, messages=msgs)
        _log_usage(r, user_id, MODEL, "precio")
        if r.stop_reason == "pause_turn":
            msgs = [msgs[0], {"role": "assistant", "content": r.content}]
            continue
        break
    txt = "".join(b.text for b in (r.content if r else []) if b.type == "text").strip()
    return txt or "No encontré precios para eso 😕"

async def handle_precio_intent(update, context, data):
    if not PRECIO_ENABLED:
        await update.message.reply_text(
            "🔧 La búsqueda de precios online está temporalmente deshabilitada "
            "(la estamos ajustando para que no consuma tanto). Probá más tarde 🙏")
        return
    query = (data.get("query") or "").strip()
    if not query:
        await update.message.reply_text("¿Precio de qué? Ej: «cuánto está el aceite Natura 1.5L»"); return
    notice = await update.message.reply_text(f"🔎 Buscando precios de «{query}»… (unos segundos)")
    try:
        res = await asyncio.to_thread(_price_search, query, current_user_id(update))
    except Exception:
        log.exception("precio")
        await notice.edit_text("No pude buscar precios ahora 🔌 Probá en un rato."); return
    await notice.edit_text(f"💲 Precios de «{query}»\n\n{res}")

async def precio_cmd(update, context):
    if not is_allowed(update): return
    q = " ".join(context.args).strip() if context.args else ""
    if not q:
        await update.message.reply_text("Usá: /precio <producto>. Ej: /precio aceite Natura 1.5L"); return
    await handle_precio_intent(update, context, {"query": q})


async def _attach_order(update, context, file_id):
    """Adjunta una imagen de orden medica al turno proximo del usuario (guarda el file_id de Telegram)."""
    uid = current_user_id(update)
    now = now_local().strftime("%Y-%m-%dT%H:%M")
    with db() as c:
        ev = c.execute("SELECT id,title FROM eventos WHERE user_id=? AND kind='turno' AND starts_at>=? ORDER BY starts_at LIMIT 1", (uid, now)).fetchone()
        if not ev:
            ev = c.execute("SELECT id,title FROM eventos WHERE user_id=? AND starts_at>=? ORDER BY starts_at LIMIT 1", (uid, now)).fetchone()
        if not ev:
            await update.message.reply_text("📎 Recibí la orden, pero no tenés un turno próximo. Creá el turno primero (ej. «turno cardiólogo el martes 10am») y reenviá la foto."); return
        c.execute("INSERT INTO event_attachments (event_id,file_id,kind) VALUES (?,?,?)", (ev["id"], file_id, "orden"))
    await update.message.reply_text(f"📎 Orden guardada en «{ev['title']}». Mirala con /orden.")

async def orden_cmd(update, context):
    """Reenvía la imagen de la orden medica guardada (del turno proximo, o por nombre)."""
    if not is_allowed(update): return
    uid = current_user_id(update)
    q = " ".join(context.args).strip() if context.args else ""
    with db() as c:
        if q:
            row = c.execute("SELECT a.file_id, e.title FROM event_attachments a JOIN eventos e ON e.id=a.event_id "
                            "WHERE e.user_id=? AND LOWER(e.title) LIKE LOWER(?) ORDER BY a.id DESC LIMIT 1", (uid, f"%{q}%")).fetchone()
        else:
            row = c.execute("SELECT a.file_id, e.title FROM event_attachments a JOIN eventos e ON e.id=a.event_id "
                            "WHERE e.user_id=? ORDER BY a.id DESC LIMIT 1", (uid,)).fetchone()
    if not row:
        await update.message.reply_text("No tenés órdenes guardadas. Mandá la foto de la orden con epígrafe «orden»."); return
    try:
        await context.bot.send_photo(chat_id=update.effective_user.id, photo=row["file_id"], caption=f"📎 Orden: {row['title']}")
    except Exception:
        log.exception("orden send")
        await update.message.reply_text("No pude reenviar la imagen 😕")


async def patrimonio_cmd(update, context):
    """Patrimonio neto: suma todos los balances valuados en ARS y USD (Takenos para USD)."""
    if not is_allowed(update): return
    uid = current_user_id(update)
    with db() as c:
        rows = c.execute(
            "SELECT a.id, a.name, a.icon, a.preferred_fx_rate, t.currency, "
            "SUM(CASE WHEN t.type='ingreso' THEN t.amount ELSE -t.amount END) AS balance "
            "FROM accounts a JOIN transactions t ON t.account_id=a.id "
            "WHERE a.active=1 AND a.user_id=? GROUP BY a.id, t.currency", (uid,)).fetchall()
    balances = [{"account_id": r["id"], "name": r["name"], "icon": r["icon"],
                 "preferred_fx_rate": r["preferred_fx_rate"], "currency": r["currency"],
                 "balance": r["balance"] or 0} for r in rows]
    if not balances:
        await update.message.reply_text("Todavia no tenes movimientos para calcular tu patrimonio."); return
    try:
        nw = networth.net_worth(balances, get_dolar_rate, _takenos_manual())
    except Exception:
        log.exception("patrimonio")
        await update.message.reply_text("No pude calcular el patrimonio ahora (cotizacion). Proba en un rato."); return
    if not nw["detail"] and nw["skipped"]:
        await update.message.reply_text("No pude obtener la cotizacion del dolar ahora 🔌 Proba en un rato."); return
    lines = ["💎 Patrimonio neto\n",
             f"≈ ${nw['total_ars']:,.2f} ARS",
             f"≈ U$D {nw['total_usd']:,.2f}\n",
             "Por cuenta:"]
    for d in nw["detail"]:
        lines.append(f"  {d['icon'] or '•'} {d['name']}: {d['balance']:,.2f} {d['currency']} (≈ ${d['value_ars']:,.0f})")
    for s in nw["skipped"]:
        lines.append(f"  {s['icon'] or '•'} {s['name']}: {s['balance']:,.2f} {s['currency']} (sin cotizacion)")
    await update.message.reply_text("\n".join(lines))


async def dolar_cmd(update, context):
    """Valor del ahorro en USD, valuado a la cotizacion Takenos (manual si existe, si no cripto)."""
    if not is_allowed(update): return
    uid = current_user_id(update)
    with db() as c:
        r = c.execute(
            "SELECT SUM(CASE WHEN type='ingreso' THEN amount ELSE -amount END) AS bal "
            "FROM transactions WHERE user_id=? AND currency='USD'", (uid,)).fetchone()
    total_usd = (r["bal"] if r and r["bal"] else 0) or 0
    manual = _takenos_manual()
    try:
        rate = fx.takenos_rate(get_dolar_rate, manual)
    except Exception:
        log.exception("dolar")
        await update.message.reply_text("No pude obtener la cotizacion ahora, proba en un rato."); return
    ars = float(total_usd) * rate
    fuente = (f"Takenos (manual ${manual:,.0f})" if manual
              else f"cripto/dolarapi ${rate:,.0f} · seteala con «el dolar takenos esta a XXXX»")
    await update.message.reply_text(
        f"💵 Tu ahorro en USD\n\n"
        f"U$D {float(total_usd):,.2f}\n"
        f"≈ ${ars:,.2f} ARS\n"
        f"(cotizacion {fuente})")


# ── Comandos nuevos (Splitwise / metas / lista / suscripciones / calendario) ──
async def balance_cmd(update, context):
    if not is_allowed(update): return
    me = current_user(update)
    if not me:
        await update.message.reply_text("No estas registrado."); return
    text, _ = balance_text_for(me)
    await update.message.reply_text(text)


async def saldar_cmd(update, context):
    if not is_allowed(update): return
    await handle_saldar_intent(update, context, {})


async def metas_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    goals = list_savings_goals(uid)
    if not goals:
        await update.message.reply_text(
            "No tenés metas de ahorro. Creá una: «quiero juntar 2000 USD para vacaciones»."); return
    out = ["🎯 Metas de ahorro\n"]
    for g in goals:
        pct = (g["current_amount"] / g["target_amount"] * 100) if g["target_amount"] else 0
        bar = finance.progress_bar(pct)
        line = (f"• {g['name']}: {g['current_amount']:,.0f}/{g['target_amount']:,.0f} {g['currency']}\n"
                f"  {bar} {pct:.0f}%")
        if g["deadline"] and pct < 100:
            months = _months_until(g["deadline"])
            sug = finance.suggested_monthly(g["target_amount"], g["current_amount"], months)
            line += f"\n  📅 {g['deadline']} · ~{sug:,.0f} {g['currency']}/mes"
        elif pct >= 100:
            line += "\n  🎉 cumplida"
        out.append(line)
    await update.message.reply_text("\n".join(out))


async def suscripciones_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    cands = recurring_candidates(uid)
    if not cands:
        await update.message.reply_text("No detecté suscripciones nuevas. Todo lo recurrente ya está agendado. 👍")
        return
    await update.message.reply_text("🔁 Posibles suscripciones detectadas:")
    for c in cands[:8]:
        txt = (f"• {c['description']} — ~{c['amount']:,.0f} {c['currency']}\n"
               f"  Aparece {c['occurrences']} veces en {c['months']} meses.")
        token = f"{c['amount']:.0f}|{c['currency']}|{c['description'][:30]}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            "📌 Agendar como recurrente", callback_data=f"subagendar:{token}")]])
        await update.message.reply_text(txt, reply_markup=kb)


async def lista_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    name = " ".join(context.args).strip() if context.args else ""
    lst = _resolve_list(name, uid, create=False)
    if not lst:
        if name:
            await update.message.reply_text(
                f"No tengo una lista «{name}». Mirá tus listas con /listas o creala diciendo «agregá X a {name}».")
        else:
            await listas_cmd(update, context)
        return
    text, kb = _render_shopping(lst["id"], lst)
    await update.message.reply_text(text, reply_markup=kb)


async def listas_cmd(update, context):
    if not is_allowed(update): return
    members = household_member_ids(current_user_id(update))
    ph = ",".join("?" for _ in members)
    with db() as c:
        rows = c.execute(
            "SELECT l.id, l.name, l.icon, l.target_date, l.recurrence, "
            "  COALESCE(SUM(CASE WHEN s.done=0 THEN 1 ELSE 0 END),0) AS pend, COUNT(s.id) AS total "
            "FROM lists l LEFT JOIN shopping_items s ON s.list_id=l.id "
            f"WHERE COALESCE(l.is_template,0)=0 AND l.owner_user_id IN ({ph}) "
            "GROUP BY l.id ORDER BY l.id", members).fetchall()
        tpls = c.execute(
            "SELECT l.name, l.icon, COUNT(s.id) AS total "
            "FROM lists l LEFT JOIN shopping_items s ON s.list_id=l.id "
            f"WHERE COALESCE(l.is_template,0)=1 AND l.owner_user_id IN ({ph}) GROUP BY l.id ORDER BY l.id", members).fetchall()
    if not rows and not tpls:
        await update.message.reply_text("No tenés listas todavia. Probá «agregá leche a la lista»."); return
    lines = ["🗂️ Tus listas", ""]
    for r in rows:
        pend, total = r["pend"] or 0, r["total"] or 0
        ic = r["icon"] or "📝"
        if not total:
            extra = "vacia"
        elif pend:
            extra = f"{pend} pendiente(s)"
        else:
            extra = "✅ completa"
        sub = _list_subtitle(dict(r))
        if sub:
            extra += f" · {sub}"
        lines.append(f"{ic} {r['name']} — {extra}")
    if tpls:
        lines.append("")
        lines.append("📋 Plantillas")
        for t in tpls:
            lines.append(f"{t['icon'] or '📋'} {t['name']} — {t['total'] or 0} ítem(s)  ·  «armá la lista de {t['name'].lower()}»")
    lines.append("")
    lines.append("Ver una: /lista <nombre>")
    await update.message.reply_text("\n".join(lines))


async def meta_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    args = context.args or []
    if len(args) < 2 or not args[-1].isdigit():
        await update.message.reply_text("Usa: /meta <habito> <veces_por_semana>\nEj: /meta gym 4"); return
    n = int(args[-1]); name = " ".join(args[:-1]).strip().lower()
    with db() as c:
        c.execute("INSERT OR REPLACE INTO user_settings (user_id, key, value) VALUES (?,?,?)",
                  (uid, f"habit_goal:{name}", str(n)))
    await update.message.reply_text(f"🎯 Meta semanal de «{name}»: {n} veces. Mirala con /habitos.")


# ── Calendario de pagos (Fase 3) ───────────────────────────────────────────
def _recurrings_for_calendar(user_id):
    """Recurrentes activas del user con su next_occurrence y nombre de cuenta."""
    with db() as c:
        rows = c.execute(
            "SELECT r.id, r.description, r.amount, r.currency, r.next_occurrence, "
            "r.user_id, a.name AS account_name "
            "FROM recurring r JOIN accounts a ON a.id=r.account_id "
            "WHERE r.active=1 AND r.user_id=? AND r.next_occurrence IS NOT NULL",
            (user_id,)).fetchall()
    return [dict(r) for r in rows]


def _cards_due_for_calendar(user_id, today):
    """Para cada tarjeta de credito activa del user, su next_due y el total del
    ciclo cerrado, via vencimientos.calcular_vencimiento."""
    with db() as c:
        cards = c.execute(
            "SELECT * FROM accounts WHERE type='credito' AND active=1 AND user_id=? ORDER BY name",
            (user_id,)).fetchall()
    out = []
    for card in cards:
        d = vencimientos.calcular_vencimiento(DB_PATH, dict(card), today)
        if d.get("error"):
            continue
        out.append({
            "account_id": d["account_id"],
            "account_name": d["account_name"],
            "user_id": d.get("user_id") or user_id,
            "next_due": d["next_due"],
            "totals": d.get("ciclo_cerrado") or [],
        })
    return out


async def proximospagos_cmd(update, context):
    if not is_allowed(update): return
    uid = current_user_id(update)
    today = now_local().date()
    recs = _recurrings_for_calendar(uid)
    cards = _cards_due_for_calendar(uid, today)
    items = proactive.upcoming_payments(recs, cards, today, horizon=30)
    await update.message.reply_text(proactive.format_calendar(items))


def _pay_button(push_item):
    """Boton inline para marcar pagada una tarjeta. callback_data = 'cardpay:<account_id>'."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        "✅ Marcar pagado", callback_data=f"cardpay:{push_item['ref_id']}")]])


async def payment_calendar_daily(context):
    try:
        import push_notify
        today = now_local().date()
        pconn = sqlite3.connect(DB_PATH); pconn.row_factory = sqlite3.Row
        for uid, tg in each_user():
            recs = _recurrings_for_calendar(uid)
            cards = _cards_due_for_calendar(uid, today)
            items = proactive.upcoming_payments(recs, cards, today, horizon=30)
            for p in proactive.due_pushes_for(items, lead_days=(3, 1)):
                kb = _pay_button(p) if p["kind"] == "card" else None
                await notify_user(context.application, tg, p["text"], reply_markup=kb)
                try:  # mismo aviso por push web (si el usuario lo activó)
                    url = "/app/tarjetas" if p.get("kind") == "card" else "/app/"
                    push_notify.send_to_user(pconn, [uid], "💳 Pago próximo", p["text"], url)
                except Exception:
                    log.exception("payment push uid=%s", uid)
        pconn.close()
    except Exception:
        log.exception("payment_calendar_daily")


# ── Resumen mensual automatico (Fase 3) ─────────────────────────────────────
def _resumen_text_for_range(user_id, date_from, date_to, shared=False):
    """Texto de resumen para [date_from, date_to]. user_id ignorado si shared=True."""
    fin = date_to + "T23:59"
    with db() as c:
        if shared:
            totales = c.execute(
                "SELECT type, currency, SUM(amount) AS t FROM transactions "
                "WHERE occurred_at>=? AND occurred_at<=? GROUP BY type, currency",
                (date_from, fin)).fetchall()
            por_cat = c.execute(
                "SELECT COALESCE(c.name,'(sin categoria)') AS cat, t.currency, SUM(t.amount) AS total "
                "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
                "WHERE t.occurred_at>=? AND t.occurred_at<=? AND t.type='gasto' "
                "GROUP BY cat, t.currency ORDER BY total DESC LIMIT 10", (date_from, fin)).fetchall()
        else:
            totales = c.execute(
                "SELECT type, currency, SUM(amount) AS t FROM transactions "
                "WHERE occurred_at>=? AND occurred_at<=? AND user_id=? GROUP BY type, currency",
                (date_from, fin, user_id)).fetchall()
            por_cat = c.execute(
                "SELECT COALESCE(c.name,'(sin categoria)') AS cat, t.currency, SUM(t.amount) AS total "
                "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
                "WHERE t.occurred_at>=? AND t.occurred_at<=? AND t.type='gasto' AND t.user_id=? "
                "GROUP BY cat, t.currency ORDER BY total DESC LIMIT 10", (date_from, fin, user_id)).fetchall()
    gastos = [t for t in totales if t["type"] == "gasto"]
    ingresos = [t for t in totales if t["type"] == "ingreso"]
    if not gastos and not ingresos:
        return None
    extra = " — compartido" if shared else ""
    msg = f"📊 Resumen mensual{extra} ({date_from} a {date_to})\n\n"
    if gastos:
        msg += "💸 Gastos\n"
        for g in gastos: msg += f"  {g['currency']}: {g['t']:,.2f}\n"
    if ingresos:
        msg += "💰 Ingresos\n"
        for i in ingresos: msg += f"  {i['currency']}: {i['t']:,.2f}\n"
    if por_cat:
        msg += "\n🏷️ Por categoria:\n"
        for cc in por_cat: msg += f"• {cc['cat']}: {cc['total']:,.2f} {cc['currency']}\n"
    return msg


async def monthly_summary_daily(context):
    try:
        today = now_local().date()
        if not proactive.should_run_monthly(today):
            return
        df, dt = proactive.last_month_range(today)
        for uid, tg in each_user():
            txt = _resumen_text_for_range(uid, df, dt, shared=False)
            if txt:
                await notify_user(context.application, tg, txt)
        users = each_user()
        if users:
            shared_txt = _resumen_text_for_range(None, df, dt, shared=True)
            if shared_txt:
                await notify_user(context.application, users[0][1], shared_txt)
    except Exception:
        log.exception("monthly_summary_daily")


# ── Alertas de dolar (Fase 3) ───────────────────────────────────────────────
async def dolar_alert_repeating(context):
    try:
        today = now_local().strftime("%Y-%m-%d")
        with db() as c:
            alerts = c.execute(
                "SELECT a.*, u.telegram_id AS tg FROM fx_alerts a "
                "LEFT JOIN users u ON u.id=a.user_id WHERE a.active=1").fetchall()
        rates = {}
        for a in alerts:
            rt = a["rate_type"] or "blue"
            if rt not in rates:
                rates[rt] = get_dolar_rate(rt)
            rate = rates[rt]
            if not proactive.fx_alert_should_fire(dict(a), rate, today=today):
                continue
            arrow = "📈" if a["direction"] == "above" else "📉"
            txt = (f"{arrow} Alerta dolar {rt}: ${rate:,.2f} "
                   f"({'supero' if a['direction']=='above' else 'bajo de'} ${a['threshold']:,.2f})")
            chat = a["tg"] or (ALLOWED_USER_IDS[0] if ALLOWED_USER_IDS else None)
            if chat:
                await notify_user(context.application, chat, txt)
            with db() as c:
                c.execute("UPDATE fx_alerts SET last_fired_at=? WHERE id=?",
                          (now_local().strftime("%Y-%m-%dT%H:%M"), a["id"]))
    except Exception:
        log.exception("dolar_alert_repeating")


# ── Snapshot diario de patrimonio (Fase 5) ──────────────────────────────────
NETWORTH_HOUR = 23  # 23:00 local: captura el cierre del dia


def _account_balances(user_id=None):
    """Lista de balances por cuenta+moneda lista para networth.net_worth."""
    rows = []
    with db() as conn:
        if user_id is None:
            accs = conn.execute(
                "SELECT id, name, icon, preferred_fx_rate FROM accounts WHERE active=1").fetchall()
        else:
            accs = conn.execute(
                "SELECT id, name, icon, preferred_fx_rate FROM accounts WHERE active=1 AND user_id=?",
                (user_id,)).fetchall()
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
                    "rate_type": fx.resolve_rate_type(a["preferred_fx_rate"], default="blue"),
                })
    return rows


def _networth_now(user_id=None):
    """Patrimonio actual usando cotizaciones en vivo."""
    balances = _account_balances(user_id)
    return networth.net_worth(balances, get_dolar_rate, takenos_manual=_takenos_manual())


async def networth_snapshot_daily(context):
    """Job diario: snapshot de patrimonio por usuario en net_worth_snapshots."""
    try:
        taken_at = now_local().strftime("%Y-%m-%dT%H:%M")
        day = taken_at[:10]
        for uid, _tg in each_user():
            try:
                res = _networth_now(uid)
                detail_json = json.dumps(res["detail"], ensure_ascii=False)
                with db() as conn:
                    existing = conn.execute(
                        "SELECT id FROM net_worth_snapshots WHERE user_id=? AND substr(taken_at,1,10)=?",
                        (uid, day)).fetchone()
                    if existing:
                        conn.execute(
                            "UPDATE net_worth_snapshots SET taken_at=?, total_ars=?, total_usd=?, detail_json=? WHERE id=?",
                            (taken_at, res["total_ars"], res["total_usd"], detail_json, existing["id"]))
                    else:
                        conn.execute(
                            "INSERT INTO net_worth_snapshots (user_id, taken_at, total_ars, total_usd, detail_json) "
                            "VALUES (?,?,?,?,?)",
                            (uid, taken_at, res["total_ars"], res["total_usd"], detail_json))
                log.info("networth snapshot uid=%s ars=%.2f usd=%.2f", uid, res["total_ars"], res["total_usd"])
            except Exception:
                log.exception("networth snapshot fallo para uid=%s", uid)
    except Exception:
        log.exception("networth_snapshot_daily fallo global")


# ── Digest semanal (Fase 1) ─────────────────────────────────────────────────
DIGEST_WEEKDAY_DEFAULT = 0   # lunes
DIGEST_HOUR = 9


def _digest_prose(facts, user_id=None):
    """LLM escribe un parrafo humano. Fallback determinista si falla."""
    try:
        resp = anthropic_client.messages.create(
            model=MODEL_SMART, max_tokens=400,
            system=("Sos un asistente de finanzas argentino. Escribi UN parrafo corto, "
                    "calido y util (rioplatense, sin tildes en exceso) resumiendo la semana "
                    "a partir de estos hechos. Menciona las categorias top, cualquier anomalia, "
                    "y cerra con UN consejo concreto. Montos en ARS. Maximo 4 oraciones."),
            messages=[{"role": "user", "content": json.dumps(facts, ensure_ascii=False)}])
        _log_usage(resp, user_id, MODEL_SMART, "digest")
        for block in resp.content:
            if getattr(block, "type", None) == "text" and block.text.strip():
                return block.text.strip()
    except Exception:
        log.exception("digest LLM fallo, uso fallback")
    return digest.digest_fallback(facts)


async def weekly_digest(context):
    try:
        today = now_local()
        with db() as conn:
            wd_row = conn.execute(
                "SELECT value FROM user_settings WHERE key='digest_weekday' LIMIT 1").fetchone()
        weekday = int(wd_row["value"]) if wd_row and wd_row["value"] is not None else DIGEST_WEEKDAY_DEFAULT
        if today.weekday() != weekday:
            return
        end = today.strftime("%Y-%m-%d")
        start = (today.date() - timedelta(days=6)).strftime("%Y-%m-%d")
        prev_end = (today.date() - timedelta(days=7)).strftime("%Y-%m-%d")
        prev_start = (today.date() - timedelta(days=13)).strftime("%Y-%m-%d")
        sql = ("SELECT COALESCE(c.name,'(sin categoria)') AS category, t.currency, "
               "SUM(t.amount) AS total, COUNT(*) AS n "
               "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
               "WHERE t.user_id=? AND t.type='gasto' AND t.occurred_at>=? AND t.occurred_at<=? "
               "GROUP BY category, t.currency")
        viars = lambda a, cur: fx.value_in_ars(a, cur, get_dolar_rate, rate_type="blue",
                                               takenos_manual=_takenos_manual())
        for user_id, telegram_id in each_user():
            with db() as conn:
                agg = conn.execute(sql, (user_id, start, end + "T23:59")).fetchall()
                prev = conn.execute(sql, (user_id, prev_start, prev_end + "T23:59")).fetchall()
            facts = digest.digest_facts(
                [{"category": r["category"], "currency": r["currency"],
                  "total": r["total"], "n": r["n"]} for r in agg],
                [{"category": r["category"], "currency": r["currency"],
                  "total": r["total"], "n": r["n"]} for r in prev],
                viars)
            prose = _digest_prose(facts, user_id)
            await notify_user(context.application, telegram_id, "🗓️ Resumen de la semana\n\n" + prose)
    except Exception:
        log.exception("weekly_digest fallo")


def main():
    init_db()
    log.info("DB lista. ALLOWED_USER_IDS=%s TZ=%s", ALLOWED_USER_IDS, TIMEZONE)
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_error_handler(on_error)
    app.add_handler(CommandHandler("patrimonio", patrimonio_cmd))
    app.add_handler(CommandHandler("dolar", dolar_cmd))
    app.add_handler(CommandHandler("precio", precio_cmd))
    app.add_handler(CommandHandler("orden", orden_cmd))
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("invitar", invitar_cmd))
    app.add_handler(CommandHandler("familia", invitar_cmd))
    app.add_handler(CommandHandler("vincular", vincular_cmd))
    app.add_handler(CommandHandler("buscar", buscar_cmd))
    app.add_handler(CommandHandler("tx", tx_cmd))
    app.add_handler(CommandHandler("resumen", resumen_cmd))
    app.add_handler(CommandHandler("cuentas", cuentas_cmd))
    app.add_handler(CommandHandler("cotizacion", cotizacion_cmd))
    app.add_handler(CommandHandler("recurrentes", recurrentes_cmd))
    app.add_handler(CommandHandler("movimientos", movimientos_cmd))
    app.add_handler(CommandHandler("borrar", borrar_cmd))
    app.add_handler(CommandHandler("tareas", tareas_cmd))
    app.add_handler(CommandHandler("done", done_cmd))
    app.add_handler(CommandHandler("habitos", habitos_cmd))
    app.add_handler(CommandHandler("pendientes", pendientes_cmd))
    app.add_handler(CommandHandler("notas", notas_cmd))
    app.add_handler(CommandHandler("password", password_cmd))
    app.add_handler(CommandHandler("addcuenta", addcuenta_cmd))
    app.add_handler(CommandHandler("compartir", compartir_cmd))
    app.add_handler(CommandHandler("compartidos", compartidos_cmd))
    app.add_handler(CommandHandler("proximospagos", proximospagos_cmd))
    app.add_handler(CommandHandler("calendario", proximospagos_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("saldar", saldar_cmd))
    app.add_handler(CommandHandler("metas", metas_cmd))
    app.add_handler(CommandHandler("suscripciones", suscripciones_cmd))
    app.add_handler(CommandHandler("lista", lista_cmd))
    app.add_handler(CommandHandler("listas", listas_cmd))
    app.add_handler(CommandHandler("meta", meta_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.job_queue.run_daily(recurring_daily, time=dtime(RECURRING_HOUR, 0, tzinfo=TZ))
    app.job_queue.run_repeating(reminder_watchdog, interval=60, first=15)
    app.job_queue.run_daily(networth_snapshot_daily, time=dtime(NETWORTH_HOUR, 0, tzinfo=TZ))
    app.job_queue.run_daily(payment_calendar_daily, time=dtime(9, 0, tzinfo=TZ))
    app.job_queue.run_daily(monthly_summary_daily, time=dtime(9, 30, tzinfo=TZ))
    app.job_queue.run_daily(weekly_digest, time=dtime(DIGEST_HOUR, 0, tzinfo=TZ))
    app.job_queue.run_repeating(dolar_alert_repeating, interval=1800, first=60)
    vencimientos.registrar_handlers(app, DB_PATH, is_allowed, current_user_id)
    log.info("Bot arrancando...")
    app.run_polling()


if __name__ == "__main__":
    main()
