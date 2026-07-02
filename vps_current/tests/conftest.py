"""
Config de pytest. Setea envs dummy ANTES de cualquier import, para que un test
que importe main.py (que en import-time lee os.environ["TELEGRAM_TOKEN"], etc.)
no crashee. Los modulos puros (fx, finance, ...) no necesitan esto.

Además expone el fixture `api`: TestClient sobre web.app con DB temporal, auth
mockeada (usuario id=1, hogar de 1, scope 'mine') y FX fijo (sin red). El schema
replica el DDL real de init_db() para las tablas que tocan los endpoints de
finanzas; migrate_kind.apply() agrega transactions.kind. Con scope 'mine' los
filtros de visibilidad se reducen a user_id=?, así que no hacen falta las
columnas `shared`.
"""
import os

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("ALLOWED_USER_IDS", "0")
os.environ.setdefault("TIMEZONE", "America/Argentina/Buenos_Aires")

import sqlite3
import pytest
from fastapi.testclient import TestClient

import web
import migrate_kind

# DDL copiado de main.init_db (transactions SIN kind: lo agrega migrate_kind).
SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER, name TEXT NOT NULL, username TEXT,
    password_hash TEXT, color TEXT, active INTEGER NOT NULL DEFAULT 1,
    household_id INTEGER, share_all INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'efectivo',
    color TEXT, icon TEXT, active INTEGER NOT NULL DEFAULT 1,
    user_id INTEGER, closing_day INTEGER, due_day INTEGER, shared INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE categories (id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'gasto',
    color TEXT, icon TEXT, active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL DEFAULT 'gasto', amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'ARS',
    account_id INTEGER NOT NULL, category_id INTEGER,
    description TEXT, occurred_at TEXT NOT NULL,
    recurring_id INTEGER, raw_message_id INTEGER, user_id INTEGER,
    is_shared INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE recurring (id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL DEFAULT 'gasto', amount REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'ARS',
    account_id INTEGER NOT NULL, category_id INTEGER, description TEXT NOT NULL,
    frequency TEXT NOT NULL DEFAULT 'monthly', day_of_month INTEGER, next_occurrence TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, total_installments INTEGER,
    installments_fired INTEGER NOT NULL DEFAULT 0, raw_message_id INTEGER, user_id INTEGER,
    shared INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE eventos (id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, starts_at TEXT NOT NULL, location TEXT, notes TEXT,
    raw_message_id INTEGER, user_id INTEGER, shared INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE recordatorios (id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL, remind_at TEXT NOT NULL, fired INTEGER NOT NULL DEFAULT 0,
    source TEXT, raw_message_id INTEGER, user_id INTEGER, event_id INTEGER, shared INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE tareas (id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'media', due_at TEXT,
    status TEXT NOT NULL DEFAULT 'pendiente', completed_at TEXT,
    raw_message_id INTEGER, user_id INTEGER, shared INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE app_meta (key TEXT PRIMARY KEY, value TEXT);
"""


@pytest.fixture
def api(tmp_path, monkeypatch):
    dbfile = tmp_path / "test.db"
    conn = sqlite3.connect(dbfile)
    conn.executescript(SCHEMA)
    migrate_kind.apply(conn)
    conn.execute("INSERT INTO users(id, telegram_id, name, username, password_hash) "
                 "VALUES (1, 111, 'Test', 'test', 'x')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(web, "DB_PATH", str(dbfile))
    monkeypatch.setattr(web, "get_dolar_rate", lambda *a, **k: 1000.0)
    web.app.dependency_overrides[web.require_user] = lambda: {
        "id": 1, "name": "Test", "household_id": None, "share_all": 0}

    client = TestClient(web.app)
    client.cookies.set("scope", "mine")
    try:
        yield Api(client, dbfile)
    finally:
        web.app.dependency_overrides.clear()


class Api:
    """Wrapper con helpers de seed que escriben directo a la DB temporal."""
    def __init__(self, client, dbfile):
        self.client = client
        self.dbfile = dbfile

    def conn(self):
        c = sqlite3.connect(self.dbfile)
        c.row_factory = sqlite3.Row
        return c

    def add_account(self, name="Banco", type="banco", user_id=1, **kw):
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO accounts(name, type, user_id, closing_day, due_day) VALUES (?,?,?,?,?)",
                (name, type, user_id, kw.get("closing_day"), kw.get("due_day")))
            c.commit()
            return cur.lastrowid

    def add_category(self, name):
        with self.conn() as c:
            cur = c.execute("INSERT INTO categories(name) VALUES (?)", (name,))
            c.commit()
            return cur.lastrowid

    def add_tx(self, account_id, amount, type="gasto", kind="normal", currency="ARS",
               occurred_at="2026-07-15T12:00", user_id=1, category_id=None, description=None):
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO transactions(type, amount, currency, account_id, category_id, "
                "description, occurred_at, user_id, kind) VALUES (?,?,?,?,?,?,?,?,?)",
                (type, amount, currency, account_id, category_id, description, occurred_at, user_id, kind))
            c.commit()
            return cur.lastrowid
