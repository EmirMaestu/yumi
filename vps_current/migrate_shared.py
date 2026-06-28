"""
Agrega columna `shared` a tareas y notas.
Lo que tiene shared=1 lo ven los dos usuarios.

Uso:
    cd ~/asistente
    sudo systemctl stop asistente
    cp data.db data.db.pre_shared.$(date +%Y%m%d_%H%M)
    ~/asistente/venv/bin/python migrate_shared.py
    sudo systemctl start asistente

Es idempotente.
"""

import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "data.db"


def main():
    if not DB.exists():
        raise SystemExit(f"ERROR: no encuentro {DB}")
    conn = sqlite3.connect(DB)
    for tbl in ("tareas", "notas"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if "shared" not in cols:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN shared INTEGER NOT NULL DEFAULT 0")
            print(f"  + {tbl}.shared")
        else:
            print(f"  . {tbl}.shared ya existia")
    conn.commit()
    conn.close()
    print("\nOK. Reinicia el bot.")


if __name__ == "__main__":
    main()
