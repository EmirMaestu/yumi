"""
Fix: la tabla `accounts` heredó del schema viejo el UNIQUE en `name`.
En multi-usuario cada persona puede tener una cuenta con el mismo nombre,
asi que recreamos la tabla sin esa restriccion.

Uso (parando el bot):
    cd ~/asistente
    sudo systemctl stop asistente asistente-web
    cp data.db data.db.pre_fix_accounts.$(date +%Y%m%d_%H%M)
    ~/asistente/venv/bin/python fix_accounts_unique.py
    sudo systemctl start asistente

Es idempotente: si el constraint ya no esta, no hace nada.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"ERROR: no encuentro {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Detectar si todavia tiene el UNIQUE
    schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='accounts'").fetchone()
    if not schema:
        raise SystemExit("ERROR: no existe la tabla accounts (??).")
    sql = schema["sql"] or ""
    if "UNIQUE" not in sql.upper() and "name TEXT NOT NULL UNIQUE" not in sql:
        # tambien chequeamos via PRAGMA
        idx = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='accounts'").fetchall()
        auto_unique = any("autoindex" in (r["name"] or "").lower() for r in idx)
        if not auto_unique:
            print("✅ La tabla accounts ya esta sin UNIQUE en name. Nada que hacer.")
            conn.close()
            return

    print("Recreando tabla accounts sin UNIQUE en `name`...")

    # PRAGMA foreign_keys = OFF para que no se rompan referencias durante la recreacion
    conn.execute("PRAGMA foreign_keys=OFF")

    conn.executescript("""
        BEGIN TRANSACTION;

        CREATE TABLE accounts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'efectivo',
            color TEXT,
            icon TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        INSERT INTO accounts_new (id, name, type, color, icon, active, user_id, created_at)
        SELECT id, name, type, color, icon, active, user_id, created_at FROM accounts;

        DROP TABLE accounts;
        ALTER TABLE accounts_new RENAME TO accounts;

        COMMIT;
    """)

    conn.execute("PRAGMA foreign_keys=ON")

    # Cuantas filas quedaron
    n = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    print(f"✅ Tabla recreada · {n} cuentas preservadas.")
    print("   Ahora Lisa puede tener su propia 'Tarjeta Santander' sin chocar con la tuya.")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
