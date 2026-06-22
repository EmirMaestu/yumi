import os
import re
import json
import base64
import sqlite3
import calendar
import difflib
import unicodedata
import logging
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from anthropic import Anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TIMEZONE = os.environ.get("TIMEZONE", "America/Argentina/Buenos_Aires")
_allowed = os.environ.get("ALLOWED_USER_ID", "").strip()
ALLOWED_USER_ID = int(_allowed) if _allowed else None
DB_PATH = BASE_DIR / "data.db"
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

anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
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

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS raw_messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER NOT NULL, tg_username TEXT, kind TEXT NOT NULL, content TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE, type TEXT NOT NULL DEFAULT 'efectivo',
            color TEXT, icon TEXT, active INTEGER NOT NULL DEFAULT 1,
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
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS eventos (id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, starts_at TEXT NOT NULL, location TEXT, notes TEXT,
            raw_message_id INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS recordatorios (id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL, remind_at TEXT NOT NULL, fired INTEGER NOT NULL DEFAULT 0,
            source TEXT, raw_message_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS tareas (id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'media', due_at TEXT,
            status TEXT NOT NULL DEFAULT 'pendiente', completed_at TEXT,
            raw_message_id INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS habito_logs (id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, value REAL, unit TEXT, note TEXT,
            logged_at TEXT NOT NULL DEFAULT (datetime('now')), raw_message_id INTEGER);
        CREATE TABLE IF NOT EXISTS notas (id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL, tags TEXT, raw_message_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE INDEX IF NOT EXISTS idx_tx_occ ON transactions(occurred_at);
        CREATE INDEX IF NOT EXISTS idx_tx_acc ON transactions(account_id);
    """)
    if conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
        conn.executemany("INSERT INTO accounts (name,type,color,icon) VALUES (?,?,?,?)", [
            ("Efectivo","efectivo","#10b981","💵"),
            ("Mercado Pago","billetera","#06b6d4","💳"),
            ("Tarjeta Santander","credito","#ef4444","🏦"),
            ("Tarjeta Naranja","credito","#f97316","🟠"),
            ("Takenos","billetera","#a855f7","🦄"),
            ("Cenco","credito","#3b82f6","🛒"),
        ])
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
    """exacto -> substring -> palabra unica -> difflib (nombre completo y por palabra)"""
    n = _norm_name(name)
    if not n: return None
    by_norm = {_norm_name(r["name"]): r for r in rows}
    if n in by_norm: return by_norm[n]
    subs = [r for k, r in by_norm.items() if n in k or k in n]
    if len(subs) == 1: return subs[0]
    # indice por palabra (solo palabras que identifican UNA sola fila)
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

def get_account_by_name(name):
    if not name: return None
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
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

def list_accounts():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM accounts WHERE active=1 ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_categories():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM categories WHERE active=1 ORDER BY type, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_transaction(tx, raw_id, recurring_id=None):
    acc = get_account_by_name(tx["account"])
    if not acc: raise ValueError(f"Cuenta no encontrada: {tx['account']}")
    cat = get_category_by_name(tx.get("category"))
    occurred_at = tx.get("occurred_at") or now_local().strftime("%Y-%m-%dT%H:%M")
    if "T" not in occurred_at: occurred_at += "T" + now_local().strftime("%H:%M")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,recurring_id,raw_message_id) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (tx.get("type","gasto"), tx["amount"], tx.get("currency","ARS"), acc["id"],
         cat["id"] if cat else None, tx.get("description"), occurred_at, recurring_id, raw_id))
    conn.commit(); tid = cur.lastrowid; conn.close()
    return tid

def save_recurring(r, raw_id, fire_immediately=True):
    import calendar as _cal
    acc = get_account_by_name(r["account"])
    if not acc: raise ValueError(f"Cuenta no encontrada: {r['account']}")
    cat = get_category_by_name(r.get("category"))
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO recurring (type,amount,currency,account_id,category_id,description,frequency,day_of_month,next_occurrence,total_installments,raw_message_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (r.get("type","gasto"), r["amount"], r.get("currency","ARS"), acc["id"],
         cat["id"] if cat else None, r["description"], r.get("frequency","monthly"),
         r.get("day_of_month"), r["next_occurrence"], r.get("total_installments"), raw_id))
    rid = cur.lastrowid
    fired_tx_id = None
    if fire_immediately:
        total = r.get("total_installments")
        cuota_str = f" (cuota 1/{total})" if total else ""
        desc_full = r["description"] + cuota_str
        occurred_at = now_local().strftime("%Y-%m-%dT%H:%M")
        cur2 = conn.execute(
            "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,recurring_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (r.get("type","gasto"), r["amount"], r.get("currency","ARS"), acc["id"],
             cat["id"] if cat else None, desc_full, occurred_at, rid))
        fired_tx_id = cur2.lastrowid
        if total and 1 >= total:
            conn.execute("UPDATE recurring SET active=0, installments_fired=1 WHERE id=?", (rid,))
        else:
            today = now_local().date()
            day = r.get("day_of_month") or today.day
            ny, nm = (today.year+1, 1) if today.month==12 else (today.year, today.month+1)
            last = _cal.monthrange(ny, nm)[1]
            d = min(day, last)
            new_next = f"{ny}-{nm:02d}-{d:02d}"
            conn.execute("UPDATE recurring SET next_occurrence=?, installments_fired=1 WHERE id=?", (new_next, rid))
    conn.commit(); conn.close()
    return rid, fired_tx_id

def save_evento(e, raw_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO eventos (title,starts_at,location,notes,raw_message_id) VALUES (?,?,?,?,?)",
        (e["title"], e["starts_at"], e.get("location"), e.get("notes"), raw_id))
    conn.commit(); eid = cur.lastrowid; conn.close()
    return eid

def save_recordatorio(text, remind_at, source=None, raw_id=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO recordatorios (text,remind_at,source,raw_message_id) VALUES (?,?,?,?)",
                       (text, remind_at, source, raw_id))
    conn.commit(); rid = cur.lastrowid; conn.close()
    return rid

def save_tarea(t, raw_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO tareas (text,priority,due_at,raw_message_id) VALUES (?,?,?,?)",
                       (t["text"], t.get("priority","media"), t.get("due_at"), raw_id))
    conn.commit(); tid = cur.lastrowid; conn.close()
    return tid

def save_habito(h, raw_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO habito_logs (name,value,unit,note,raw_message_id) VALUES (?,?,?,?,?)",
                       (h["name"].lower(), h.get("value"), h.get("unit"), h.get("note"), raw_id))
    conn.commit(); hid = cur.lastrowid; conn.close()
    return hid

def save_nota(n, raw_id):
    tags = json.dumps(n.get("tags") or [], ensure_ascii=False)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO notas (text,tags,raw_message_id) VALUES (?,?,?)",
                       (n["text"], tags, raw_id))
    conn.commit(); nid = cur.lastrowid; conn.close()
    return nid

def compute_next_monthly(current_iso, day_of_month):
    cur = datetime.fromisoformat(current_iso).date()
    ny, nm = (cur.year+1, 1) if cur.month == 12 else (cur.year, cur.month+1)
    last = calendar.monthrange(ny, nm)[1]
    d = min(day_of_month or cur.day, last)
    return f"{ny}-{nm:02d}-{d:02d}"

def is_allowed(update):
    if ALLOWED_USER_ID is None: return True
    return update.effective_user.id == ALLOWED_USER_ID

def _strip_json(content):
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"): content = content[4:]
        content = content.strip()
    return content


def build_filter(filters):
    where = []
    params = []
    f = filters or {}
    if f.get('ids'):
        placeholders = ','.join(['?'] * len(f['ids']))
        where.append(f"t.id IN ({placeholders})")
        params.extend([int(x) for x in f['ids']])
    if f.get('description_contains'):
        where.append("LOWER(COALESCE(t.description,'')) LIKE LOWER(?)")
        params.append(f"%{f['description_contains']}%")
    if f.get('current_account'):
        acc = get_account_by_name(f['current_account'])
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


def query_transactions(filters):
    where, params, order, limit = build_filter(filters)
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
        with urllib.request.urlopen(url, timeout=5) as r:
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
                            "evento","recordatorio","tarea","habito","nota","consulta","desconocido"]},
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

PARSER_TEMPLATE = """Sos el parser de un asistente personal en español rioplatense (finanzas, agenda, tareas, hábitos, notas).
Tu ÚNICA salida es la tool `registrar_acciones` con un array `acciones`.

HOY: __TODAY__ (__DOW__) · HORA: __NOW__ · TZ: __TZ__

CUENTAS DISPONIBLES (usá el nombre EXACTO en `account`):
__ACCOUNTS__

CATEGORÍAS:
__CATEGORIES__

═══ REGLA DE ORO: SIEMPRE UN ARRAY ═══
Un mensaje puede traer VARIAS acciones de tipos DISTINTOS (gasto + recordatorio + nota, etc).
Detectá CADA una y devolvé un elemento del array por acción. Si hay una sola, array de 1.
Separadores típicos: "y", "también", "además", "y anotá", "y recordame", saltos de línea, viñetas (-, •, *).
JAMÁS sumes montos de items distintos ni fusiones acciones: cada item con monto = una transacción propia.
Si varios items comparten cuenta/fecha dicha una sola vez, propagala a TODOS.

═══ TABLA DE DECISIÓN (aplicar en orden) ═══
1. Verbo en pasado sobre dinero ("pagué","gasté","compré","cobré","me pagaron") → transaccion
2. Verbo en pasado sobre actividad personal ("hice","entrené","leí","corrí","medité") → habito
3. Movimiento entre dos cuentas propias ("pasé/convertí/mandé de X a Y") → transferencia
4. Pago repetido o en cuotas ("todos los meses","N cuotas","agendá <servicio>") → recurrente
5. "recordame/avisame/acordame" + momento futuro → recordatorio. Con fecha u hora explícita es SIEMPRE recordatorio, NUNCA tarea.
6. Cita con persona/lugar/hora ("cena con","turno","reunión") → evento
7. Pendiente accionable SIN momento exacto ("tengo que","hay que") → tarea
8. "anotá/apuntá/acordate que/idea:" (información, no acción futura) → nota
9. Pregunta sobre sus datos ("cuánto gasté","qué tengo") → consulta
10. "borrá/mové/editá/cambiá" con #IDs o filtros → eliminar/mover/editar
11. Nada matchea → desconocido con data.aclaracion = UNA pregunta concreta para el usuario

Distinciones finas:
- "recordame pagar X" SIN cuándo → tarea (no hay momento para avisar)
- "tengo que pagar X el viernes a las 9" → recordatorio (hay momento exacto)
- "pagué la luz" sin monto → desconocido preguntando el monto

═══ MONTOS (ARGENTINA) ═══
"luca"=1000 → "50 lucas"=50000 · "media luca"=500 · "palo"=1000000 → "1,5 palos"=1500000
"gamba"=100 · "2k"=2000 · "1.500"=1500 (punto = miles) · "dólares/USD/u$s/verdes" → USD · default ARS

═══ FECHAS (resolver TODO a ISO usando HOY=__TODAY__ __DOW__) ═══
"mañana"=+1d · "pasado mañana"=+2d · "en una hora"=__NOW__+1h
"el viernes"=viernes más próximo futuro · "el viernes que viene"=viernes de la semana siguiente
"fin de mes"=último día del mes · recordatorio sin hora → 09:00

═══ CAMPOS DE `data` SEGÚN intent ═══
transaccion: {"type":"gasto"|"ingreso","amount":num,"currency":"ARS"|"USD"|"EUR","category":str,"account":str,"description":str,"occurred_at":"YYYY-MM-DDTHH:MM"}
transferencia: {"amount":num,"from_account":str,"to_account":str,"from_currency":str,"to_currency":str,"exchange_rate":num|null,"rate_type":"oficial"|"blue"|"mep"|"cripto"|null,"description":str,"occurred_at":"YYYY-MM-DDTHH:MM"}
recurrente: {"type":"gasto"|"ingreso","amount":num,"currency":str,"category":str,"account":str,"description":str,"frequency":"monthly","day_of_month":num,"next_occurrence":"YYYY-MM-DD","total_installments":num|null}
mover: {"target_account":str|null,"target_category":str|null,"filters":{"ids":[int]|null,"description_contains":str|null,"current_account":str|null,"current_category":str|null,"type":str|null,"currency":str|null,"date_from":"YYYY-MM-DD"|null,"date_to":"YYYY-MM-DD"|null,"limit":int|null,"order":"newest"|"oldest"|null}}
eliminar: {"filters": misma forma que mover.filters}
editar: {"id":int,"amount":num|null,"currency":str|null,"description":str|null,"category":str|null,"account":str|null,"occurred_at":str|null}
evento: {"title":str,"starts_at":"YYYY-MM-DDTHH:MM","location":str|null,"notes":str|null}
recordatorio: {"text":str,"remind_at":"YYYY-MM-DDTHH:MM"}
tarea: {"text":str,"priority":"baja"|"media"|"alta","due_at":"YYYY-MM-DD"|null}
habito: {"name":str,"value":num|null,"unit":str|null,"note":str|null}
nota: {"text":str,"tags":[str]|null}
consulta: {"type":"resumen"|"transacciones"|"recurrentes"|"cuentas"|"eventos"|"tareas"|"habitos"|"notas"|"pendientes"|"cotizacion"|"otro","period":str|null}
desconocido: {"aclaracion":str}

ALIAS de cuentas: mp/mercadopago→Mercado Pago · santander/santi→Tarjeta Santander · naranja→Tarjeta Naranja · cenco→Cenco · tk→Takenos · cash/plata→Efectivo
Categoría: inferila (nafta/uber/sube→Transporte · super/verdulería→Comida · resto/café/delivery→Comida afuera · luz/gas/internet→Servicios · netflix/spotify→Suscripciones · farmacia→Salud). Sin señal → Otros.
Gasto chico sin cuenta dicha → account="Efectivo", confidence 0.7.
confidence: 0.9+ inequívoco · 0.6-0.85 algún campo inferido · <0.5 mejor desconocido.

═══ EJEMPLOS ═══
"recordame mañana a las 11am pagar el internet"
→ acciones=[{"intent":"recordatorio","confidence":0.97,"data":{"text":"Pagar el internet","remind_at":"<mañana>T11:00"}}]
(JAMÁS tarea: hay "recordame" + momento explícito)

"recordame mañana 11 pagar internet y anotá que el plan nuevo sale 30 lucas"
→ 2 acciones: recordatorio{text:"Pagar internet",remind_at:"<mañana>T11:00"} + nota{text:"El plan nuevo de internet sale $30.000",tags:["internet"]}

"gasté 5 lucas en nafta y 2 en el kiosco, todo con santander"
→ 2 transacciones: {amount:5000,category:"Transporte",account:"Tarjeta Santander",description:"Nafta"} y {amount:2000,category:"Comida",account:"Tarjeta Santander",description:"Kiosco"}

"agregá estos gastos a naranja:
- 36500 nafta
- 78637.65 asado
y un recurrente movistar 7000 el 10"
→ 3 acciones: transaccion(36500,Transporte), transaccion(78637.65,Comida afuera), recurrente(7000,day_of_month:10,category:"Servicios",description:"Movistar")

"cena con Ana el viernes 21hs en Palermo y recordame comprar vino ese día a las 18"
→ evento{title:"Cena con Ana",starts_at:"<viernes>T21:00",location:"Palermo"} + recordatorio{text:"Comprar vino",remind_at:"<viernes>T18:00"}

"hice 40 min de ejercicio y leí 20 páginas"
→ habito{name:"ejercicio",value:40,unit:"min"} + habito{name:"lectura",value:20,unit:"páginas"}

"compré la heladera 800 lucas en 12 cuotas con santander y anotá que la entregan el sábado"
→ recurrente{amount:800000,total_installments:12,account:"Tarjeta Santander",category:"Hogar",description:"Heladera"} + nota{text:"La heladera la entregan el sábado"}

"el otro día estuvo bueno lo de marcos"
→ [{"intent":"desconocido","confidence":0.3,"data":{"aclaracion":"¿Lo guardo como nota o era otra cosa?"}}]"""


def _accs_block(): return "\n".join(f"- {a['name']} ({a['type']})" for a in list_accounts())
def _cats_block(): return "\n".join(f"- {c['name']} [{c['type']}]" for c in list_categories())

def build_parser_system():
    now = now_local()
    return (PARSER_TEMPLATE
            .replace("__ACCOUNTS__", _accs_block())
            .replace("__CATEGORIES__", _cats_block())
            .replace("__TODAY__", now.strftime("%Y-%m-%d"))
            .replace("__NOW__", now.strftime("%H:%M"))
            .replace("__TZ__", TIMEZONE)
            .replace("__DOW__", DIAS_ES[now.weekday()]))


_NUM_RE = r"(\d+(?:[.,]\d+)?)"

def normalize_amounts(text):
    """'50 lucas'->'50000', '1,5 palos'->'1500000', '2k'->'2000' antes de Claude."""
    def f(v): return float(v.replace(",", "."))
    t = text
    t = re.sub(rf"{_NUM_RE}\s*palos?\b", lambda m: str(int(f(m.group(1)) * 1000000)), t, flags=re.I)
    t = re.sub(rf"{_NUM_RE}\s*lucas?\b", lambda m: str(int(f(m.group(1)) * 1000)), t, flags=re.I)
    t = re.sub(r"\bmedia\s+luca\b", "500", t, flags=re.I)
    t = re.sub(rf"{_NUM_RE}\s*gambas?\b", lambda m: str(int(f(m.group(1)) * 100)), t, flags=re.I)
    t = re.sub(rf"\b{_NUM_RE}k\b", lambda m: str(int(f(m.group(1)) * 1000)), t, flags=re.I)
    return t


def parse_intent(text):
    """v2: devuelve SIEMPRE una lista de acciones [{'intent': X, X: data, 'confidence': c}].
    Haiku primero; si duda o no entiende, reintenta con Sonnet."""
    text = normalize_amounts(text)
    system = build_parser_system()

    def call(model):
        resp = anthropic_client.messages.create(
            model=model, max_tokens=2000, system=system,
            messages=[{"role": "user", "content": text}],
            tools=[PARSER_TOOL],
            tool_choice={"type": "tool", "name": "registrar_acciones"})
        for block in resp.content:
            if block.type == "tool_use":
                return block.input.get("acciones") or []
        return []

    acciones = call(MODEL)
    dudoso = (not acciones) or all(
        a.get("intent") == "desconocido" or (a.get("confidence") or 1) < 0.5 for a in acciones)
    if dudoso:
        try:
            retry = call(MODEL_SMART)
            if retry and not all(a.get("intent") == "desconocido" for a in retry):
                acciones = retry
                log.info("Parser escalado a %s", MODEL_SMART)
        except Exception:
            log.exception("Escalado a Sonnet falló, sigo con Haiku")

    out = []
    for a in acciones:
        intent = a.get("intent", "desconocido")
        out.append({"intent": intent, intent: a.get("data") or {}, "confidence": a.get("confidence")})
    return out


PHOTO_TEMPLATE = """Eres un parser de comprobantes en español rioplatense.
Recibís una imagen (ticket, factura, captura de MercadoPago/banco, etc) y extraés transacciones.

CUENTAS (elegí UNA por transacción, exacta):
__ACCOUNTS__

CATEGORÍAS:
__CATEGORIES__

Devolvés EXCLUSIVAMENTE:
{"transacciones":[{"type":"gasto"|"ingreso","amount":number,"currency":"ARS"|"USD"|"EUR","category":string,"account":string,"description":string,"occurred_at":"YYYY-MM-DDTHH:MM"}]}

Reglas:
- Si la imagen muestra UN solo monto -> una transacción. Lista de movimientos -> una por cada uno.
- Si no identificás nada -> "transacciones":[].
- ARS default.
- account: priorizá lo que diga el caption del usuario. Si no, deducí del header/logo. Ticket físico -> Efectivo.
- INVERSIONES: si la descripción del item menciona "inversión","oro","bonos","cripto","plazo fijo","acciones","FCI","ETF","Bonar","AL30","GD30" -> account = "Inversiones" (incluso si el header del extracto era otra cuenta).
- TRANSFERENCIAS: si el item dice "Pago de tarjeta X" o "Cambio USD a ARS", category = "Transferencia".
- occurred_at: fecha del comprobante si es visible; sino __TODAY__T12:00.
- description: comercio/concepto, max 50 chars.
- UN solo JSON."""

def parse_photo(image_bytes, caption=""):
    now = now_local()
    system = (PHOTO_TEMPLATE
              .replace("__ACCOUNTS__", _accs_block())
              .replace("__CATEGORIES__", _cats_block())
              .replace("__TODAY__", now.strftime("%Y-%m-%d")))
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    user_text = "Extraé las transacciones de esta imagen."
    if caption: user_text += f"\n\nContexto del usuario: «{caption}»"
    resp = anthropic_client.messages.create(model=MODEL, max_tokens=1024, system=system,
        messages=[{"role":"user","content":[
            {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b64}},
            {"type":"text","text":user_text}
        ]}])
    return json.loads(_strip_json(resp.content[0].text))


def fmt_dt(s):
    if 'T' not in s: s += "T00:00"
    d = datetime.fromisoformat(s)
    return f"{DIAS_ES[d.weekday()]} {d.strftime('%d/%m %H:%M')}"

def fmt_d(s):
    d = datetime.fromisoformat(s if 'T' in s else s+"T00:00")
    return f"{DIAS_ES[d.weekday()]} {d.strftime('%d/%m')}"


async def send_reminder(context):
    data = context.job.data
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT fired FROM recordatorios WHERE id=?", (data["rem_id"],)).fetchone()
    if row and row[0]:
        conn.close(); return  # ya lo mando el watchdog u otro job
    try:
        await context.bot.send_message(chat_id=data["chat_id"], text=f"⏰ {data['text']}")
    finally:
        conn.execute("UPDATE recordatorios SET fired=1 WHERE id=?", (data["rem_id"],))
        conn.commit(); conn.close()

def schedule_reminder(job_queue, rem_id, text, remind_at_str, chat_id):
    dt = parse_local(remind_at_str)
    delay = (dt - now_local()).total_seconds()
    if delay <= 0: return None
    return job_queue.run_once(callback=send_reminder, when=delay,
        data={"rem_id":rem_id,"text":text,"chat_id":chat_id}, name=f"reminder_{rem_id}")

def reschedule_pending(app):
    if not ALLOWED_USER_ID: return
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id,text,remind_at FROM recordatorios WHERE fired=0 ORDER BY remind_at").fetchall()
    conn.close()
    n=0
    for rem_id, text, remind_at in rows:
        if schedule_reminder(app.job_queue, rem_id, text, remind_at, ALLOWED_USER_ID): n+=1
    log.info("Recordatorios reagendados: %d", n)


async def recurring_daily(context):
    if not ALLOWED_USER_ID: return
    today_str = now_local().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    due = conn.execute("SELECT * FROM recurring WHERE active=1 AND next_occurrence <= ?", (today_str,)).fetchall()
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
                "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,recurring_id) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (r['type'], r['amount'], r['currency'], r['account_id'], r['category_id'],
                 desc_full, occurred_at, r['id']))
            tx_id = cur.lastrowid
            if r['frequency'] == 'monthly':
                next_dt = compute_next_monthly(r['next_occurrence'], r['day_of_month'])
                if total and new_fired >= total:
                    conn.execute("UPDATE recurring SET active=0, installments_fired=? WHERE id=?", (new_fired, r['id']))
                else:
                    conn.execute("UPDATE recurring SET next_occurrence=?, installments_fired=? WHERE id=?", (next_dt, new_fired, r['id']))
            conn.commit(); conn.close()
            sign = "💸" if r['type'] == 'gasto' else "💰"
            cierre = "\n\n✅ Última cuota cobrada, recurrente finalizada." if (total and new_fired >= total) else ""
            msg = (f"🔁 Recurrente generada{cuota_str}\n{sign} {r['amount']:,.2f} {r['currency']} — {r['description']}\n"
                   f"📂 {acc['name']}")
            if cat_row: msg += f" · 🏷️ {cat_row['name']}"
            msg += cierre
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar (no se cobró)", callback_data=f"txcancel:{tx_id}")]])
            await context.bot.send_message(chat_id=ALLOWED_USER_ID, text=msg, reply_markup=kb)
        except Exception:
            log.exception("Error procesando recurrente %s", r['id'])


async def callback_handler(update, context):
    q = update.callback_query
    parts = q.data.split(":", 1)
    if len(parts) != 2:
        await q.answer(); return
    action, arg = parts
    base_text = q.message.text or ""

    if action == "tdone":
        try:
            tid = int(arg)
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE tareas SET status='hecha', completed_at=datetime('now') WHERE id=?", (tid,))
            conn.commit(); conn.close()
            await q.answer(f"✓ Tarea #{tid} hecha")
        except Exception:
            log.exception("tdone"); await q.answer("Error", show_alert=True)
        return

    if action == "tdel":
        try:
            tid = int(arg)
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM tareas WHERE id=?", (tid,))
            conn.commit(); conn.close()
            await q.answer(f"× Tarea #{tid} borrada")
        except Exception:
            log.exception("tdel"); await q.answer("Error", show_alert=True)
        return

    if action == "txdel":
        try:
            tid = int(arg)
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
            conn.commit(); conn.close()
            await q.answer("🗑️ Borrada")
            await q.edit_message_text(base_text + "\n\n🗑️ Borrada.")
        except Exception:
            log.exception("txdel"); await q.answer("Error", show_alert=True)
        return

    if action == "rectoggle":
        try:
            rid = int(arg)
            conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT active FROM recurring WHERE id=?", (rid,)).fetchone()
            if row:
                new_active = 0 if row['active'] else 1
                conn.execute("UPDATE recurring SET active=? WHERE id=?", (new_active, rid))
                conn.commit()
            conn.close()
            await q.answer("Estado cambiado")
        except Exception:
            log.exception("rectoggle"); await q.answer("Error", show_alert=True)
        return

    if action == "recdel":
        try:
            rid = int(arg)
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM recurring WHERE id=?", (rid,))
            conn.commit(); conn.close()
            await q.answer("🗑️ Borrada")
        except Exception:
            log.exception("recdel"); await q.answer("Error", show_alert=True)
        return

    if action == "remdel":
        try:
            rid = int(arg)
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE recordatorios SET fired=1 WHERE id=?", (rid,))
            conn.commit(); conn.close()
            await q.answer("⏰ Cancelado")
        except Exception:
            log.exception("remdel"); await q.answer("Error", show_alert=True)
        return

    await q.answer()

    if action == "txcancel":
        try:
            tx_id = int(arg)
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
            conn.commit(); conn.close()
            await q.edit_message_text(base_text + "\n\n❌ Cancelado, no se cobró.")
        except Exception:
            log.exception("Cancel fail")
    elif action == "movok":
        op = PENDING_OPS.pop(arg, None)
        if not op: await q.edit_message_text(base_text + "\n\n⚠️ Operación expirada."); return
        n = apply_move(op['ids'], op.get('target_account_id'), op.get('target_category_id'))
        await q.edit_message_text(base_text + f"\n\n✅ Movidas {n} transacciones.")
    elif action == "movno":
        PENDING_OPS.pop(arg, None)
        await q.edit_message_text(base_text + "\n\n❌ Cancelado.")
    elif action == "delok":
        op = PENDING_OPS.pop(arg, None)
        if not op: await q.edit_message_text(base_text + "\n\n⚠️ Operación expirada."); return
        n = apply_delete(op['ids'])
        await q.edit_message_text(base_text + f"\n\n🗑️ Borradas {n} transacciones.")
    elif action == "delno":
        PENDING_OPS.pop(arg, None)
        await q.edit_message_text(base_text + "\n\n❌ Cancelado.")


async def post_init(app):
    reschedule_pending(app)


async def help_cmd(update, context):
    if not is_allowed(update): return
    await update.message.reply_text(
        "📚 Comandos\n\n"
        "💸 Transacciones\n"
        "  /movimientos [N] /tx N /borrar N /cuentas /cotizacion\n\n"
        "🔁 Recurrentes\n"
        "  /recurrentes (con botones)\n\n"
        "✅ Tareas\n"
        "  /tareas (con botones) /done N\n\n"
        "💪 Hábitos · /habitos\n"
        "⏰ Recordatorios · /pendientes\n"
        "📓 Notas · /notas [busqueda]\n"
        "🔍 Búsqueda global · /buscar TEXTO\n"
        "📊 Resumen del mes · /resumen\n\n"
        "También entiendo natural:\n"
        "  «pagué 1000 con MP»\n"
        "  «mové todos los gastos a Takenos»\n"
        "  «editá monto de #42 a 5000»\n"
        "  «cambiá descripción de #15 a luz junio»\n"
        "  «borrá #20» o «borrá los gastos de Naranja»"
    )


async def buscar_cmd(update, context):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Usá: /buscar TEXTO"); return
    q = " ".join(context.args).strip()
    if len(q) < 2:
        await update.message.reply_text("Mínimo 2 caracteres."); return
    like = f"%{q}%"
    out = [f"🔍 «{q}»"]
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    txs = conn.execute(
        "SELECT t.id,t.type,t.amount,t.currency,t.description,t.occurred_at,a.name AS acc "
        "FROM transactions t JOIN accounts a ON a.id=t.account_id "
        "WHERE LOWER(COALESCE(t.description,'')) LIKE LOWER(?) "
        "ORDER BY t.occurred_at DESC LIMIT 5", (like,)).fetchall()
    if txs:
        out.append("\n💸 Transacciones:")
        for r in txs:
            sign = "+" if r['type']=='ingreso' else "-"; emoji = "🟢" if r['type']=='ingreso' else "🔴"
            d = datetime.fromisoformat(r['occurred_at']).strftime("%d/%m")
            out.append(f"  {emoji} #{r['id']} {d} {sign}{r['amount']:,.2f} {r['currency']} · {r['description'] or ''} ({r['acc']})")
    tas = conn.execute("SELECT id,text,status FROM tareas WHERE text LIKE ? ORDER BY id DESC LIMIT 5", (like,)).fetchall()
    if tas:
        out.append("\n✅ Tareas:")
        for r in tas:
            icon = "✓" if r['status']=='hecha' else "○"
            out.append(f"  {icon} #{r['id']} {r['text']}")
    nts = conn.execute("SELECT id,text,created_at FROM notas WHERE text LIKE ? ORDER BY created_at DESC LIMIT 5", (like,)).fetchall()
    if nts:
        out.append("\n📓 Notas:")
        for r in nts:
            snip = r['text'][:100] + ("…" if len(r['text'])>100 else "")
            d = datetime.fromisoformat(r['created_at']).strftime("%d/%m")
            out.append(f"  #{r['id']} {d}: {snip}")
    evs = conn.execute("SELECT id,title,starts_at FROM eventos WHERE title LIKE ? ORDER BY starts_at DESC LIMIT 5", (like,)).fetchall()
    if evs:
        out.append("\n📅 Eventos:")
        for r in evs:
            d = datetime.fromisoformat(r['starts_at']).strftime("%d/%m %H:%M")
            out.append(f"  #{r['id']} {d}: {r['title']}")
    res = conn.execute("SELECT id,text,remind_at,fired FROM recordatorios WHERE text LIKE ? ORDER BY remind_at DESC LIMIT 5", (like,)).fetchall()
    if res:
        out.append("\n⏰ Recordatorios:")
        for r in res:
            d = datetime.fromisoformat(r['remind_at']).strftime("%d/%m %H:%M")
            icon = "✓" if r['fired'] else "⏳"
            out.append(f"  {icon} #{r['id']} {d}: {r['text']}")
    conn.close()
    if len(out) == 1: out.append("\nSin resultados.")
    await update.message.reply_text("\n".join(out))


async def tx_cmd(update, context):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Usá: /tx N"); return
    try: tid = int(context.args[0].lstrip("#"))
    except ValueError: await update.message.reply_text("Pasame un número."); return
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT t.*, a.name AS acc_name, a.icon AS acc_icon, c.name AS cat_name, c.icon AS cat_icon "
        "FROM transactions t JOIN accounts a ON a.id=t.account_id "
        "LEFT JOIN categories c ON c.id=t.category_id WHERE t.id=?", (tid,)).fetchone()
    conn.close()
    if not row: await update.message.reply_text(f"No encontré #{tid}"); return
    sign = "+" if row['type']=='ingreso' else "-"; emoji = "🟢" if row['type']=='ingreso' else "🔴"
    d = datetime.fromisoformat(row['occurred_at'])
    cat_str = f"{row['cat_icon'] or ''} {row['cat_name']}" if row['cat_name'] else "(sin categoría)"
    msg = (f"{emoji} Transacción #{row['id']}\n\n"
           f"💵 {sign}{row['amount']:,.2f} {row['currency']}\n"
           f"📝 {row['description'] or '(sin descripción)'}\n"
           f"📂 {row['acc_icon'] or ''} {row['acc_name']}\n"
           f"🏷️ {cat_str}\n"
           f"📅 {DIAS_ES[d.weekday()]} {d.strftime('%d/%m/%Y %H:%M')}\n\n"
           f"Para editar decime: «editá monto/descripción/categoría/cuenta de #{tid} a X»")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Borrar", callback_data=f"txdel:{tid}")]])
    await update.message.reply_text(msg, reply_markup=kb)


async def comandos_cmd(update, context):
    if not is_allowed(update): return
    msg = (
        "🛠️ Comandos del VPS\n\n"
        "🔌 Conectarte desde Windows (PowerShell):\n"
        "`ssh emir@217.76.48.219`\n\n"
        "🤖 Bot (asistente):\n"
        "• Reiniciar: `sudo systemctl restart asistente`\n"
        "• Logs: `sudo journalctl -u asistente -n 30 --no-pager`\n"
        "• Estado: `sudo systemctl status asistente --no-pager | head -15`\n\n"
        "🌐 Web dashboard:\n"
        "• Reiniciar: `sudo systemctl restart asistente-web`\n"
        "• Logs: `sudo journalctl -u asistente-web -n 30 --no-pager`\n\n"
        "🔒 Caddy (HTTPS):\n"
        "• Reload config: `sudo systemctl reload caddy`\n"
        "• Logs: `sudo journalctl -u caddy -n 30 --no-pager`\n\n"
        "📁 Archivos clave:\n"
        "• Bot: `~/asistente/main.py`\n"
        "• Web: `~/asistente/web.py`\n"
        "• DB: `~/asistente/data.db`\n"
        "• Config: `~/asistente/.env`\n"
        "• Caddyfile: `/etc/caddy/Caddyfile`\n\n"
        "🌎 URL del dashboard:\n"
        "https://asistente.emir-maestu.site\n\n"
        "💾 Backup rápido de la DB:\n"
        "`cp ~/asistente/data.db ~/asistente/data.db.$(date +%Y%m%d)`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def start_cmd(update, context):
    if not is_allowed(update): return
    await update.message.reply_text(
        "Soy tu asistente. Mandame texto, audios o fotos:\n\n"
        "💸 «pagué 1000 coca cola con MP» / foto de un ticket\n"
        "💰 «me pagaron 500 USD takenos sueldo»\n"
        "🔁 «agendá Movistar 7000 todos los 10 con MP»\n"
        "🔀 «mové todos los gastos a takenos» / «pasá #42 a Cenco»\n"
        "🗑️ «borrá el gasto de la luz»\n"
        "📅 «cena con Ana viernes 21»\n"
        "⏰ «recordame mañana 9 llamar al banco»\n"
        "✅ «tengo que pagar la luz»\n"
        "💪 «hice 30 min de ejercicio»\n"
        "📓 «anotá: idea para X»\n\n"
        "Comandos:\n/resumen /cuentas /recurrentes /movimientos /borrar N\n"
        "/tareas /done N /habitos /pendientes /notas")


async def resumen_cmd(update, context):
    if not is_allowed(update): return
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    now = now_local(); mes_ini = now.strftime("%Y-%m-01")
    totales = conn.execute(
        "SELECT type, currency, SUM(amount) AS t FROM transactions WHERE occurred_at>=? GROUP BY type, currency",
        (mes_ini,)).fetchall()
    por_cat = conn.execute(
        "SELECT COALESCE(c.name,'(sin categoría)') AS cat, t.currency, SUM(t.amount) AS total "
        "FROM transactions t LEFT JOIN categories c ON c.id=t.category_id "
        "WHERE t.occurred_at>=? AND t.type='gasto' GROUP BY cat, t.currency ORDER BY total DESC LIMIT 10",
        (mes_ini,)).fetchall()
    por_acc = conn.execute(
        "SELECT a.name AS acc, t.currency, SUM(t.amount) AS total FROM transactions t "
        "JOIN accounts a ON a.id=t.account_id WHERE t.occurred_at>=? AND t.type='gasto' "
        "GROUP BY a.name, t.currency ORDER BY total DESC", (mes_ini,)).fetchall()
    eventos = conn.execute(
        "SELECT title,starts_at,location FROM eventos WHERE starts_at>=? ORDER BY starts_at LIMIT 5",
        (now.strftime("%Y-%m-%dT%H:%M"),)).fetchall()
    conn.close()
    msg = f"📊 Resumen — {MESES_ES[now.month-1]} {now.year}\n\n"
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
        msg += "\n🏷️ Por categoría:\n"
        for c in por_cat: msg += f"• {c['cat']}: {c['total']:,.2f} {c['currency']}\n"
    if por_acc:
        msg += "\n💳 Por cuenta:\n"
        for a in por_acc: msg += f"• {a['acc']}: {a['total']:,.2f} {a['currency']}\n"
    msg += "\n📅 Próximos eventos\n"
    if eventos:
        for title,starts_at,loc in eventos:
            line = f"• {fmt_dt(starts_at)} — {title}"
            if loc: line += f" ({loc})"
            msg += line + "\n"
    else: msg += "Nada agendado.\n"
    await update.message.reply_text(msg)


async def cuentas_cmd(update, context):
    if not is_allowed(update): return
    accs = list_accounts()
    if not accs: await update.message.reply_text("Sin cuentas configuradas."); return
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
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT r.*, a.name AS acc_name, c.name AS cat_name FROM recurring r "
        "JOIN accounts a ON a.id=r.account_id LEFT JOIN categories c ON c.id=r.category_id "
        "WHERE r.active=1 ORDER BY r.next_occurrence LIMIT 15").fetchall()
    conn.close()
    if not rows: await update.message.reply_text("Sin recurrentes activas."); return
    msg = "🔁 Recurrentes activas\n\n"
    kb_rows = []
    for r in rows:
        sign = "💸" if r['type']=='gasto' else "💰"
        cuota_info = ""
        if r['total_installments']:
            cuota_info = f" · 🧾 cuota {(r['installments_fired'] or 0)+1}/{r['total_installments']}"
        msg += f"{sign} #{r['id']} {r['description']} — {r['amount']:,.2f} {r['currency']}{cuota_info}\n"
        msg += f"   📂 {r['acc_name']}"
        if r['cat_name']: msg += f" · 🏷️ {r['cat_name']}"
        msg += f"\n   📅 Día {r['day_of_month']} · próxima: {r['next_occurrence']}\n\n"
        kb_rows.append([
            InlineKeyboardButton(f"⏸ #{r['id']}", callback_data=f"rectoggle:{r['id']}"),
            InlineKeyboardButton(f"× #{r['id']}", callback_data=f"recdel:{r['id']}"),
        ])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb_rows))


async def movimientos_cmd(update, context):
    if not is_allowed(update): return
    n = 15
    if context.args:
        try: n = min(max(int(context.args[0]), 1), 50)
        except ValueError: pass
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT t.id, t.type, t.amount, t.currency, t.description, t.occurred_at, "
        "a.name AS acc, c.name AS cat FROM transactions t "
        "JOIN accounts a ON a.id=t.account_id LEFT JOIN categories c ON c.id=t.category_id "
        "ORDER BY DATE(t.occurred_at) DESC, t.id DESC LIMIT ?", (n,)).fetchall()
    conn.close()
    if not rows: await update.message.reply_text("Sin movimientos."); return
    msg = f"\U0001F4CB Últimos {len(rows)} movimientos:\n"
    current_day = None
    for r in rows:
        d = datetime.fromisoformat(r['occurred_at'])
        day_str = f"{DIAS_ES[d.weekday()]} {d.strftime('%d/%m')}"
        if day_str != current_day:
            msg += f"\n\U0001F4C5 {day_str}\n"
            current_day = day_str
        emoji = "\U0001F7E2" if r['type']=='ingreso' else "\U0001F534"
        sign = "+" if r['type']=='ingreso' else "-"
        line = f"{emoji} #{r['id']} {sign}{r['amount']:,.2f} {r['currency']}"
        if r['description']: line += f" · {r['description']}"
        line += f"\n   \U0001F4C2 {r['acc']}"
        if r['cat']: line += f" · \U0001F3F7\uFE0F {r['cat']}"
        msg += line + "\n"
    msg += "\n/borrar N para borrar una"
    await update.message.reply_text(msg)

async def borrar_cmd(update, context):
    if not is_allowed(update): return
    if not context.args:
        await update.message.reply_text("Usá: /borrar <id> (de /movimientos)"); return
    try: tid = int(context.args[0].lstrip("#"))
    except ValueError: await update.message.reply_text("Pasame un número."); return
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT amount,currency,description FROM transactions WHERE id=?", (tid,)).fetchone()
    if not row: conn.close(); await update.message.reply_text(f"No encontré #{tid}"); return
    conn.execute("DELETE FROM transactions WHERE id=?", (tid,)); conn.commit(); conn.close()
    await update.message.reply_text(f"🗑️ #{tid} borrada: {row['amount']:,.2f} {row['currency']} {row['description'] or ''}")


async def tareas_cmd(update, context):
    if not is_allowed(update): return
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id,text,priority,due_at FROM tareas WHERE status='pendiente' "
        "ORDER BY CASE priority WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, "
        "COALESCE(due_at,'9999'), id LIMIT 20").fetchall()
    conn.close()
    if not rows: await update.message.reply_text("Sin tareas pendientes 🎉"); return
    icons = {"alta":"🔴","media":"🟡","baja":"🟢"}
    msg = "✅ Tareas pendientes\n\n"
    for tid,text,pri,due in rows:
        line = f"{icons.get(pri,'⚪')} #{tid} {text}"
        if due: line += f" — vence {fmt_d(due)}"
        msg += line + "\n"
    kb_rows = []
    for tid,text,pri,due in rows:
        short = (text[:20]+"…") if len(text)>20 else text
        kb_rows.append([
            InlineKeyboardButton(f"✓ #{tid}", callback_data=f"tdone:{tid}"),
            InlineKeyboardButton(f"× #{tid}", callback_data=f"tdel:{tid}"),
        ])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb_rows))


async def done_cmd(update, context):
    if not is_allowed(update): return
    if not context.args: await update.message.reply_text("Usá: /done <id>"); return
    try: tid = int(context.args[0].lstrip("#"))
    except ValueError: await update.message.reply_text("Pasame un número."); return
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT text,status FROM tareas WHERE id=?", (tid,)).fetchone()
    if not row: conn.close(); await update.message.reply_text(f"No encontré la tarea #{tid}"); return
    if row[1] == "hecha": conn.close(); await update.message.reply_text(f"#{tid} ya estaba hecha."); return
    conn.execute("UPDATE tareas SET status='hecha', completed_at=datetime('now') WHERE id=?", (tid,))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Hecho: {row[0]}")


async def habitos_cmd(update, context):
    if not is_allowed(update): return
    desde = (now_local() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT name,COUNT(*),SUM(value),unit FROM habito_logs WHERE logged_at>=? "
        "GROUP BY name,unit ORDER BY 2 DESC", (desde,)).fetchall()
    conn.close()
    if not rows: await update.message.reply_text("Sin hábitos en últimos 7 días."); return
    msg = "💪 Hábitos — últimos 7 días\n\n"
    for name,count,total,unit in rows:
        if total and unit: msg += f"• {name}: {count}x ({total:g} {unit})\n"
        else: msg += f"• {name}: {count}x\n"
    await update.message.reply_text(msg)


async def pendientes_cmd(update, context):
    if not is_allowed(update): return
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id,text,remind_at,source FROM recordatorios WHERE fired=0 ORDER BY remind_at LIMIT 15").fetchall()
    conn.close()
    if not rows: await update.message.reply_text("Sin recordatorios pendientes ✨"); return
    msg = "⏰ Próximos recordatorios\n\n"
    kb_rows = []
    for r in rows:
        tag = " (evento)" if r['source']=="evento" else ""
        msg += f"• #{r['id']} {fmt_dt(r['remind_at'])} — {r['text']}{tag}\n"
        kb_rows.append([InlineKeyboardButton(f"× cancelar #{r['id']}", callback_data=f"remdel:{r['id']}")])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb_rows))


async def notas_cmd(update, context):
    if not is_allowed(update): return
    q = " ".join(context.args).strip() if context.args else None
    conn = sqlite3.connect(DB_PATH)
    if q:
        rows = conn.execute("SELECT id,text,created_at FROM notas WHERE text LIKE ? ORDER BY created_at DESC LIMIT 10",(f"%{q}%",)).fetchall()
        header = f"📓 Notas con «{q}»\n\n"
    else:
        rows = conn.execute("SELECT id,text,created_at FROM notas ORDER BY created_at DESC LIMIT 10").fetchall()
        header = "📓 Últimas notas\n\n"
    conn.close()
    if not rows: await update.message.reply_text("Sin notas."); return
    msg = header
    for nid,text,created in rows:
        snip = text if len(text)<200 else text[:200]+"…"
        d = datetime.fromisoformat(created).strftime("%d/%m %H:%M")
        msg += f"#{nid} ({d})\n{snip}\n\n"
    await update.message.reply_text(msg)


async def handle_move_intent(update, context, mv):
    target_acc = get_account_by_name(mv.get('target_account')) if mv.get('target_account') else None
    target_cat = get_category_by_name(mv.get('target_category')) if mv.get('target_category') else None
    if not target_acc and not target_cat:
        await update.message.reply_text("No entendí a qué cuenta o categoría mover. Decímelo más explícito."); return
    if mv.get('target_account') and not target_acc:
        await update.message.reply_text(f"No conozco la cuenta '{mv['target_account']}'."); return

    rows = query_transactions(mv.get('filters') or {})
    if not rows:
        await update.message.reply_text("No encontré transacciones que coincidan con eso."); return

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
    extra = f"\n... y {len(rows)-5} más" if len(rows)>5 else ""
    text = title + ":\n\n" + "\n".join(preview_lines(rows,5)) + extra
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar", callback_data=f"movok:{op_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"movno:{op_id}"),
    ]])
    await update.message.reply_text(text, reply_markup=kb)


async def handle_delete_intent(update, context, dl):
    rows = query_transactions(dl.get('filters') or {})
    if not rows:
        await update.message.reply_text("No encontré transacciones que coincidan."); return
    ids = [r['id'] for r in rows]
    if len(rows) == 1:
        apply_delete(ids)
        r = rows[0]
        sign = "-" if r['type']=='gasto' else "+"
        await update.message.reply_text(f"🗑️ Borrada: #{r['id']} {sign}{r['amount']:,.2f} {r['currency']} «{r['description'] or ''}»"); return
    op_id = make_op_id()
    PENDING_OPS[op_id] = {"kind":"delete","ids":ids}
    extra = f"\n... y {len(rows)-5} más" if len(rows)>5 else ""
    text = f"⚠️ Voy a BORRAR {len(rows)} transacciones:\n\n" + "\n".join(preview_lines(rows,5)) + extra
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar borrado", callback_data=f"delok:{op_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"delno:{op_id}"),
    ]])
    await update.message.reply_text(text, reply_markup=kb)


async def handle_transferencia_intent(update, context, tr, raw_id):
    from_acc = get_account_by_name(tr.get("from_account"))
    to_acc = get_account_by_name(tr.get("to_account"))
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
                      "occurred_at":occurred_at}, raw_id)
    save_transaction({"type":"ingreso","amount":to_amount,"currency":to_cur,"account":to_acc["name"],
                      "category":"Transferencia","description":f"{description} <- {from_acc['name']}",
                      "occurred_at":occurred_at}, raw_id)
    msg = f"🔁 Transferencia\n-{amount:,.2f} {from_cur} de {from_acc['name']}\n+{to_amount:,.2f} {to_cur} a {to_acc['name']}"
    if rate and from_cur != to_cur:
        msg += f"\n💱 @ {rate:,.2f} ({tr.get('rate_type') or 'blue'})"
    await update.message.reply_text(msg)


async def cotizacion_cmd(update, context):
    if not is_allowed(update): return
    msg = "💱 Cotización USD\n\n"
    for t in ["oficial","blue","mep","cripto"]:
        rate = get_dolar_rate(t)
        msg += f"{t.capitalize()}: " + (f"${rate:,.2f}" if rate else "no disponible") + "\n"
    await update.message.reply_text(msg)


async def handle_editar_intent(update, context, ed):
    if not ed.get("id"):
        await update.message.reply_text("¿Editar qué? Decime el #ID."); return
    tid = int(ed["id"])
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    if not row:
        conn.close(); await update.message.reply_text(f"No encontré la transacción #{tid}"); return
    fields = []; params = []; changes = []
    if ed.get("amount") is not None:
        fields.append("amount=?"); params.append(ed["amount"]); changes.append(f"monto={ed['amount']:,.2f}")
    if ed.get("currency"):
        fields.append("currency=?"); params.append(ed["currency"]); changes.append(f"moneda={ed['currency']}")
    if ed.get("description"):
        fields.append("description=?"); params.append(ed["description"]); changes.append(f"descripción=«{ed['description']}»")
    if ed.get("account"):
        acc = get_account_by_name(ed["account"])
        if not acc:
            conn.close(); await update.message.reply_text(f"No conozco la cuenta '{ed['account']}'."); return
        fields.append("account_id=?"); params.append(acc["id"]); changes.append(f"cuenta={acc['name']}")
    if ed.get("category"):
        cat = get_category_by_name(ed["category"])
        if not cat:
            conn.close(); await update.message.reply_text(f"No conozco la categoría '{ed['category']}'."); return
        fields.append("category_id=?"); params.append(cat["id"]); changes.append(f"categoría={cat['name']}")
    if ed.get("occurred_at"):
        fields.append("occurred_at=?"); params.append(ed["occurred_at"]); changes.append(f"fecha={ed['occurred_at']}")
    if not fields:
        conn.close(); await update.message.reply_text("No me dijiste qué cambiar."); return
    params.append(tid)
    conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id=?", params)
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ #{tid} actualizada\n" + "\n".join(f"   • {c}" for c in changes))


async def process_text(update, context, text, raw_id):
    try:
        acciones = parse_intent(text)
    except Exception as e:
        log.exception("Error parseando intent")
        await update.message.reply_text(f"No pude entender eso 😕\n({e})"); return
    if not acciones:
        await update.message.reply_text("No estoy seguro de qué hacer con eso. /start para ejemplos."); return
    if len(acciones) > 1:
        await update.message.reply_text(f"📦 Entendí {len(acciones)} acciones:")
    for parsed in acciones:
        try:
            await process_action(update, context, parsed, raw_id)
        except Exception as e:
            log.exception("Error en acción %s", parsed.get("intent"))
            await update.message.reply_text(f"✗ Error en acción «{parsed.get('intent')}»: {e}")


async def process_action(update, context, parsed, raw_id):
    intent = parsed.get("intent")

    if intent == "transaccion" and parsed.get("transaccion"):
        txs = parsed["transaccion"]
        if not isinstance(txs, list): txs = [txs]
        for tx in txs:
            try: save_transaction(tx, raw_id)
            except Exception as e:
                log.exception("Save tx fail")
                await update.message.reply_text(f"No pude guardar la transacción 😕\n({e})"); continue
            sign = "💸" if tx.get('type','gasto')=='gasto' else "💰"
            reply = f"{sign} {tx['amount']:,.2f} {tx.get('currency','ARS')}"
            if tx.get('description'): reply += f" — {tx['description']}"
            reply += f"\n📂 {tx['account']}"
            if tx.get('category'): reply += f" · 🏷️ {tx['category']}"
            await update.message.reply_text(reply)

    elif intent == "recurrente" and parsed.get("recurrente"):
        r = parsed["recurrente"]
        if not r.get("next_occurrence"): r["next_occurrence"] = now_local().strftime("%Y-%m-%d")
        if not r.get("description"): r["description"] = "recurrente"
        try: save_recurring(r, raw_id)
        except Exception as e:
            log.exception("Save rec fail")
            await update.message.reply_text(f"No pude agendar la recurrente 😕\n({e})"); return
        sign = "💸" if r.get('type','gasto')=='gasto' else "💰"
        cuota_extra = f" · {r.get('total_installments')} cuotas" if r.get('total_installments') else ""
        reply = (f"🔁 Recurrente agendada{cuota_extra}\n"
                 f"{sign} {r['amount']:,.2f} {r.get('currency','ARS')} — {r['description']}\n"
                 f"📂 {r['account']}\n"
                 f"📅 Cada mes el día {r.get('day_of_month')} · próxima: {r['next_occurrence']}")
        await update.message.reply_text(reply)

    elif intent == "transferencia" and parsed.get("transferencia"):
        await handle_transferencia_intent(update, context, parsed["transferencia"], raw_id)

    elif intent == "editar" and parsed.get("editar"):
        await handle_editar_intent(update, context, parsed["editar"])

    elif intent == "mover" and parsed.get("mover"):
        await handle_move_intent(update, context, parsed["mover"])

    elif intent == "eliminar" and parsed.get("eliminar"):
        await handle_delete_intent(update, context, parsed["eliminar"])

    elif intent == "evento" and parsed.get("evento"):
        e = parsed["evento"]; save_evento(e, raw_id)
        reply = f"📅 {e['title']} — {fmt_dt(e['starts_at'])}"
        if e.get("location"): reply += f"\n📍 {e['location']}"
        try:
            start_dt = parse_local(e["starts_at"])
            remind_dt = start_dt - timedelta(minutes=EVENT_REMINDER_MIN)
            if remind_dt > now_local():
                rstr = remind_dt.strftime("%Y-%m-%dT%H:%M")
                rid = save_recordatorio(f"En {EVENT_REMINDER_MIN} min: {e['title']}", rstr, source="evento", raw_id=raw_id)
                schedule_reminder(context.application.job_queue, rid, f"En {EVENT_REMINDER_MIN} min: {e['title']}", rstr, update.effective_user.id)
                reply += f"\n🔔 Te aviso {EVENT_REMINDER_MIN} min antes."
        except Exception: log.exception("Reminder fail")
        await update.message.reply_text(reply)

    elif intent == "recordatorio" and parsed.get("recordatorio"):
        r = parsed["recordatorio"]
        rid = save_recordatorio(r["text"], r["remind_at"], source="manual", raw_id=raw_id)
        ok = schedule_reminder(context.application.job_queue, rid, r["text"], r["remind_at"], update.effective_user.id)
        if ok: await update.message.reply_text(f"⏰ Te recuerdo: «{r['text']}»\n📅 {fmt_dt(r['remind_at'])}")
        else: await update.message.reply_text("⚠️ Esa fecha ya pasó.")

    elif intent == "tarea" and parsed.get("tarea"):
        t = parsed["tarea"]; tid = save_tarea(t, raw_id)
        icon = {"alta":"🔴","media":"🟡","baja":"🟢"}.get(t.get("priority","media"),"🟡")
        reply = f"{icon} Tarea #{tid}: {t['text']}"
        if t.get("due_at"): reply += f"\n📅 vence {fmt_d(t['due_at'])}"
        reply += f"\n(/done {tid} cuando esté hecha)"
        await update.message.reply_text(reply)

    elif intent == "habito" and parsed.get("habito"):
        h = parsed["habito"]; save_habito(h, raw_id)
        bits = [f"💪 {h['name']}"]
        if h.get("value") and h.get("unit"): bits.append(f"{h['value']:g} {h['unit']}")
        await update.message.reply_text(" — ".join(bits) + " ✓")

    elif intent == "nota" and parsed.get("nota"):
        n = parsed["nota"]; nid = save_nota(n, raw_id)
        await update.message.reply_text(f"📓 Nota #{nid} guardada.")

    elif intent == "consulta":
        ctype = (parsed.get("consulta") or {}).get("type","")
        if ctype == "pendientes": await pendientes_cmd(update, context)
        elif ctype == "tareas": await tareas_cmd(update, context)
        elif ctype == "habitos": await habitos_cmd(update, context)
        elif ctype == "notas": await notas_cmd(update, context)
        elif ctype == "recurrentes": await recurrentes_cmd(update, context)
        elif ctype == "cuentas": await cuentas_cmd(update, context)
        elif ctype == "transacciones": await movimientos_cmd(update, context)
        elif ctype == "cotizacion": await cotizacion_cmd(update, context)
        else: await resumen_cmd(update, context)

    else:
        data = parsed.get("desconocido") or {}
        aclaracion = data.get("aclaracion") if isinstance(data, dict) else None
        await update.message.reply_text(aclaracion or
            "No estoy seguro. Si era un gasto, mencioná la cuenta (ej. «pagué 1000 coca cola con MP»). /start para ejemplos.")


async def handle_text(update, context):
    if not is_allowed(update): return
    user = update.effective_user; text = update.message.text
    raw_id = save_raw(user.id, user.username, "text", text)
    await process_text(update, context, text, raw_id)


async def handle_voice(update, context):
    if not is_allowed(update): return
    voice = update.message.voice
    notice = await update.message.reply_text("🎙️ Transcribiendo...")
    ogg_path = VOICE_DIR / f"{voice.file_id}.ogg"
    try:
        file = await context.bot.get_file(voice.file_id)
        await file.download_to_drive(ogg_path)
        segments, _ = get_whisper().transcribe(str(ogg_path), language="es", vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
    except Exception as e:
        log.exception("Voice error"); await notice.edit_text(f"Falló transcripción 😕\n({e})"); return
    finally:
        try: ogg_path.unlink()
        except Exception: pass
    if not text: await notice.edit_text("No te entendí en el audio."); return
    await notice.edit_text(f"📝 «{text}»")
    user = update.effective_user
    raw_id = save_raw(user.id, user.username, "voice", text)
    await process_text(update, context, text, raw_id)


async def handle_photo(update, context):
    if not is_allowed(update): return
    photo = update.message.photo[-1]
    caption = (update.message.caption or "").strip()
    notice = await update.message.reply_text("📸 Analizando imagen...")
    img_path = PHOTO_DIR / f"{photo.file_id}.jpg"
    try:
        file = await context.bot.get_file(photo.file_id)
        await file.download_to_drive(img_path)
        with open(img_path, "rb") as f: image_bytes = f.read()
        parsed = parse_photo(image_bytes, caption)
    except Exception as e:
        log.exception("Photo error"); await notice.edit_text(f"Falló el análisis 😕\n({e})"); return
    finally:
        try: img_path.unlink()
        except Exception: pass

    txs = parsed.get("transacciones", [])
    user = update.effective_user
    raw_id = save_raw(user.id, user.username, "photo",
                      json.dumps({"caption":caption,"parsed":parsed}, ensure_ascii=False))
    if not txs: await notice.edit_text("No identifiqué transacciones en la imagen."); return
    saved = []
    for tx in txs:
        try: save_transaction(tx, raw_id); saved.append(tx)
        except Exception: log.exception("Error guardando tx de foto")
    if not saved: await notice.edit_text("Detecté transacciones pero no pude guardarlas."); return
    if len(saved) == 1:
        tx = saved[0]
        sign = "💸" if tx.get('type','gasto')=='gasto' else "💰"
        m = f"{sign} {tx['amount']:,.2f} {tx.get('currency','ARS')}"
        if tx.get('description'): m += f" — {tx['description']}"
        m += f"\n📂 {tx['account']}"
        if tx.get('category'): m += f" · 🏷️ {tx['category']}"
    else:
        m = f"📸 {len(saved)} transacciones cargadas:\n\n"
        for tx in saved:
            sign = "-" if tx.get('type','gasto')=='gasto' else "+"
            m += f"{sign}{tx['amount']:,.2f} {tx.get('currency','ARS')} — {tx.get('description','')}\n   📂 {tx['account']}\n"
        m += "\nSi alguna quedó en cuenta equivocada, decime ej. «pasá #N a Takenos»"
    await notice.edit_text(m)


async def reminder_watchdog(context):
    """Cada 60s: dispara recordatorios vencidos y no disparados.
    Cubre los creados desde el dashboard (el JobQueue no los conoce)
    y los que se perdieron por un reinicio."""
    if not ALLOWED_USER_ID: return
    try:
        conn = sqlite3.connect(DB_PATH)
        nowstr = now_local().strftime("%Y-%m-%dT%H:%M")
        rows = conn.execute(
            "SELECT id, text, source FROM recordatorios "
            "WHERE fired=0 AND REPLACE(remind_at,' ','T') <= ? ORDER BY remind_at LIMIT 10",
            (nowstr,)).fetchall()
        for rid, rtext, source in rows:
            conn.execute("UPDATE recordatorios SET fired=1 WHERE id=?", (rid,))
            conn.commit()
            extra = " (desde la web)" if source == "web" else ""
            await context.bot.send_message(chat_id=ALLOWED_USER_ID, text=f"⏰ {rtext}{extra}")
        conn.close()
    except Exception:
        log.exception("watchdog")


def main():
    init_db()
    log.info("DB lista. ALLOWED_USER_ID=%s TZ=%s", ALLOWED_USER_ID, TIMEZONE)
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("comandos", comandos_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
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
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.job_queue.run_daily(recurring_daily, time=dtime(RECURRING_HOUR, 0, tzinfo=TZ))
    app.job_queue.run_repeating(reminder_watchdog, interval=60, first=15)
    log.info("Bot arrancando…")
    app.run_polling()


if __name__ == "__main__":
    main()
