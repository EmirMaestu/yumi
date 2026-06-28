#!/usr/bin/env python3
"""Corrige cuotas migradas con la convencion vieja (+1 mes) en tarjetas donde el
vencimiento es el MISMO mes que el cierre (due_day > closing_day). Resta 1 mes.
Uso: python fix_venc_samemonth.py <db> [--apply]"""
import sqlite3, sys, calendar
from datetime import date

def shift_month(d, n):
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))

def main():
    db = sys.argv[1]; apply = "--apply" in sys.argv
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT r.id, r.description, r.next_occurrence, r.day_of_month,
               a.name AS cuenta, a.closing_day, a.due_day
        FROM recurring r JOIN accounts a ON a.id=r.account_id
        WHERE r.active=1 AND r.total_installments IS NOT NULL
          AND a.type='credito' AND a.closing_day IS NOT NULL AND a.due_day IS NOT NULL
          AND a.due_day > a.closing_day          -- vence el mismo mes
          AND r.day_of_month = a.due_day         -- ya migrado a vencimiento
        ORDER BY r.id
    """).fetchall()
    if not rows:
        print("Nada para corregir."); return
    n = 0
    for r in rows:
        occ = date.fromisoformat(r["next_occurrence"][:10])
        new_occ = shift_month(occ, -1).isoformat()
        print(f"  #{r['id']:>2} {r['cuenta']:<22} {r['description'][:22]:<22} "
              f"next {r['next_occurrence'][:10]} -> {new_occ}")
        if apply:
            conn.execute("UPDATE recurring SET next_occurrence=? WHERE id=?", (new_occ, r["id"]))
        n += 1
    if apply:
        conn.commit(); print(f"APLICADO: {n} corregidos.")
    else:
        print(f"DRY-RUN: {n} se corregirian (--apply para escribir).")
    conn.close()

if __name__ == "__main__":
    main()
