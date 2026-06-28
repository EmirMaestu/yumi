#!/usr/bin/env python3
"""Migra cuotas de tarjeta cierre-fechadas -> vencimiento.
Uso: python migrate_cuotas_venc.py <db_path> [--apply]
Sin --apply = dry-run (solo muestra). Con --apply = escribe.
Criterio: recurrente activo, con total_installments (cuota), cuenta credito con
closing_day Y due_day, closing_day != due_day, y day_of_month == closing_day
(o sea, fechado en el cierre). Mueve next_occurrence al vencimiento del cierre
y day_of_month -> due_day.
"""
import sqlite3, sys, calendar
from datetime import date

def safe_day(y, m, d):
    return min(d, calendar.monthrange(y, m)[1])

def main():
    if len(sys.argv) < 2:
        print("falta db_path"); sys.exit(1)
    db = sys.argv[1]
    apply = "--apply" in sys.argv
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT r.id, r.description, r.next_occurrence, r.day_of_month,
               a.name AS cuenta, a.closing_day, a.due_day
        FROM recurring r JOIN accounts a ON a.id=r.account_id
        WHERE r.active=1 AND r.total_installments IS NOT NULL
          AND a.type='credito' AND a.closing_day IS NOT NULL AND a.due_day IS NOT NULL
          AND a.closing_day <> a.due_day
          AND r.day_of_month = a.closing_day
        ORDER BY r.id
    """).fetchall()
    if not rows:
        print("Nada para migrar."); return
    n = 0
    for r in rows:
        occ = date.fromisoformat(r["next_occurrence"][:10])  # fecha de cierre actual
        dd = r["due_day"]
        vy = occ.year + (1 if occ.month == 12 else 0)
        vm = 1 if occ.month == 12 else occ.month + 1
        new_occ = date(vy, vm, safe_day(vy, vm, dd)).isoformat()
        print(f"  #{r['id']:>2} {r['cuenta']:<22} {r['description'][:24]:<24} "
              f"next {r['next_occurrence'][:10]} -> {new_occ}   dom {r['day_of_month']} -> {dd}")
        if apply:
            conn.execute("UPDATE recurring SET next_occurrence=?, day_of_month=? WHERE id=?",
                         (new_occ, dd, r["id"]))
        n += 1
    if apply:
        conn.commit(); print(f"APLICADO: {n} recurrentes migrados.")
    else:
        print(f"DRY-RUN: {n} recurrentes se migrarían (usá --apply para escribir).")
    conn.close()

if __name__ == "__main__":
    main()
