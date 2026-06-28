"""
Agrega closing_day y due_day a la tabla accounts.
Despues te pregunta interactivamente por cada tarjeta de credito existente
cuales son sus dias de cierre y vencimiento.

Uso (parando el bot):
    cd ~/asistente
    sudo systemctl stop asistente asistente-web
    cp data.db data.db.pre_tarjetas.$(date +%Y%m%d_%H%M)
    ~/asistente/venv/bin/python migrate_tarjetas.py
    sudo systemctl start asistente

Es idempotente. Si la columna ya existe no la duplica.
Si una tarjeta ya tiene closing_day, te pregunta si la cambias o saltas.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"ERROR: no encuentro {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1) Columnas
    cols = [r[1] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()]
    if "closing_day" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN closing_day INTEGER")
        print("  + accounts.closing_day")
    else:
        print("  · accounts.closing_day ya existia")
    if "due_day" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN due_day INTEGER")
        print("  + accounts.due_day")
    else:
        print("  · accounts.due_day ya existia")
    conn.commit()

    # 2) Tarjetas de credito
    cards = conn.execute(
        "SELECT a.id, a.name, a.user_id, a.closing_day, a.due_day, u.name AS owner "
        "FROM accounts a LEFT JOIN users u ON u.id=a.user_id "
        "WHERE a.type='credito' AND a.active=1 ORDER BY u.name, a.name"
    ).fetchall()

    if not cards:
        print("\nNo hay tarjetas de credito activas. Listo.")
        conn.close()
        return

    print(f"\nEncontre {len(cards)} tarjetas de credito.")
    print("Para cada una, ingresa cierre y vencimiento (numeros del 1 al 28).")
    print("Enter en blanco = saltar / dejar como esta.\n")

    def ask_int(prompt, current):
        suffix = f" [actual: {current}]" if current else ""
        while True:
            raw = input(f"  {prompt}{suffix}: ").strip()
            if not raw:
                return current
            if not raw.isdigit():
                print("    Tiene que ser un numero (1-28).")
                continue
            n = int(raw)
            if 1 <= n <= 28:
                return n
            print("    Entre 1 y 28 (asi no rompe en febrero).")

    for c in cards:
        owner = f" ({c['owner']})" if c['owner'] else ""
        print(f"\n→ {c['name']}{owner}")
        cd = ask_int("Dia de cierre", c['closing_day'])
        dd = ask_int("Dia de vencimiento", c['due_day'])
        conn.execute("UPDATE accounts SET closing_day=?, due_day=? WHERE id=?",
                     (cd, dd, c['id']))
        if cd and dd:
            print(f"    OK: cierra dia {cd}, vence dia {dd}")
        elif not cd and not dd:
            print(f"    sin cambios")

    conn.commit()
    conn.close()
    print("\nMigracion lista.")
    print("Recorda subir vencimientos.py y aplicar los parches en main.py / web.py.")


if __name__ == "__main__":
    main()
