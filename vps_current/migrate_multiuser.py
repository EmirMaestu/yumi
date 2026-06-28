"""
Migración a multi-usuario.

Uso (correr UNA sola vez en el VPS, parado el bot):
    cd ~/asistente
    sudo systemctl stop asistente asistente-web
    cp data.db data.db.pre_multiuser.$(date +%Y%m%d_%H%M)   # backup
    python3 migrate_multiuser.py
    sudo systemctl start asistente asistente-web

Qué hace:
  1. Crea tabla `users` con dos filas: Emir (vos) y Lisa.
  2. Agrega columna `user_id` a: accounts, transactions, recurring,
     eventos, recordatorios, tareas, habito_logs, notas.
  3. Todo lo que ya existía queda asignado a Emir.
  4. categories queda compartida (sin user_id).

Es idempotente: si ya corrió, no hace nada destructivo.
"""

import os
import sqlite3
import hashlib
import secrets
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "data.db"

# ─── CONFIG ───────────────────────────────────────────────────────────────
EMIR_TG = int(os.environ.get("ALLOWED_USER_ID", "0"))
LISA_TG = 6655744140

EMIR_NAME = "Emir"
LISA_NAME = "Lisa"

# username y password por defecto. Las pueden cambiar después con /password.
EMIR_USERNAME = "emir"
LISA_USERNAME = "lisa"
DEFAULT_PASSWORD_EMIR = os.environ.get("EMIR_PASSWORD", "cambiame123")
DEFAULT_PASSWORD_LISA = os.environ.get("LISA_PASSWORD", "cambiame123")


def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def column_exists(conn, table, column):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def add_column_if_missing(conn, table, column_def, column_name):
    if not column_exists(conn, table, column_name):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
        print(f"  + {table}.{column_name}")
    else:
        print(f"  · {table}.{column_name} ya existía")


def main():
    if EMIR_TG == 0:
        raise SystemExit("ERROR: ALLOWED_USER_ID no está en .env, no puedo identificar a Emir.")
    if not DB_PATH.exists():
        raise SystemExit(f"ERROR: no encuentro {DB_PATH}")

    print(f"DB: {DB_PATH}")
    print(f"Emir tg_id: {EMIR_TG}")
    print(f"Lisa tg_id: {LISA_TG}")
    print()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1) Tabla users
    print("[1/4] Tabla users…")
    conn.execute("""
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
    """)

    def upsert_user(tg_id, name, username, password, color):
        row = conn.execute("SELECT id FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
        if row:
            print(f"  · {name} ya existía (id={row['id']})")
            return row['id']
        cur = conn.execute(
            "INSERT INTO users (telegram_id, name, username, password_hash, color) VALUES (?,?,?,?,?)",
            (tg_id, name, username, hash_password(password), color))
        uid = cur.lastrowid
        print(f"  + {name} creado (id={uid}, usuario={username}, password={password})")
        return uid

    emir_id = upsert_user(EMIR_TG, EMIR_NAME, EMIR_USERNAME, DEFAULT_PASSWORD_EMIR, "#3b82f6")
    lisa_id = upsert_user(LISA_TG, LISA_NAME, LISA_USERNAME, DEFAULT_PASSWORD_LISA, "#ec4899")
    conn.commit()

    # 2) Agregar columnas user_id
    print("\n[2/4] Columnas user_id…")
    tables_with_user = [
        "accounts", "transactions", "recurring",
        "eventos", "recordatorios", "tareas",
        "habito_logs", "notas",
    ]
    for tbl in tables_with_user:
        add_column_if_missing(conn, tbl, "user_id INTEGER", "user_id")

    # 3) Asignar a Emir todo lo que tiene user_id NULL
    print(f"\n[3/4] Asignando datos existentes a Emir (id={emir_id})…")
    for tbl in tables_with_user:
        cur = conn.execute(f"UPDATE {tbl} SET user_id=? WHERE user_id IS NULL", (emir_id,))
        print(f"  · {tbl}: {cur.rowcount} filas")
    conn.commit()

    # 4) Índices útiles
    print("\n[4/4] Índices…")
    for tbl in tables_with_user:
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_user ON {tbl}(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_tg ON users(telegram_id)")
    conn.commit()
    conn.close()

    print("\n✅ Migración completa.")
    print(f"\nCredenciales del dashboard (cambialas con /password en Telegram):")
    print(f"  Emir → usuario: {EMIR_USERNAME} · pass: {DEFAULT_PASSWORD_EMIR}")
    print(f"  Lisa → usuario: {LISA_USERNAME} · pass: {DEFAULT_PASSWORD_LISA}")
    print(f"\nActualizá tu .env:")
    print(f"  ALLOWED_USER_IDS={EMIR_TG},{LISA_TG}")
    print(f"  (podés dejar ALLOWED_USER_ID viejo, el bot lo soporta como fallback)")


if __name__ == "__main__":
    main()
