"""
Fix: el patcher v2 dejó callback_handler sin la rama 'phct:' (los botones
de la foto). Esto la inserta correctamente.

Uso:
    cd ~/asistente
    sudo systemctl stop asistente
    ~/asistente/venv/bin/python apply_photo_cuotas_v2_fix.py
    sudo systemctl start asistente
"""

import re, shutil
from datetime import datetime
from pathlib import Path

MAIN = Path(__file__).parent / "main.py"
MARK = "# >>> photo cuotas v2 fix"

CALLBACK_BRANCH = '''    # >>> photo cuotas v2
    if action == "phct":
        try:
            choice, op_id = arg.split(":", 1)
        except ValueError:
            await q.answer(); return
        op = PENDING_OPS.pop(op_id, None)
        if not op:
            await q.edit_message_text(base_text + "\\n\\n⚠️ Esta operación ya expiró o se resolvió.")
            return
        if choice == "cancel":
            await q.edit_message_text(base_text + "\\n\\n❌ Cancelado.")
            return
        if choice == "skip":
            await q.edit_message_text(base_text + "\\n\\n⏭ Salteada (no se cargó nada).")
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
                    base_text + f"\\n\\n❌ No tengo la cuenta '{op.get('account','')}' "
                    f"creada para vos. Creala con /addcuenta y volvé a mandar la foto.")
                return
            cat = get_category_by_name(op.get("category","Otros"))

            conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
            day = now_local().day
            next_occ = compute_next_monthly(now_local().strftime("%Y-%m-%d"), day)

            cur = conn.execute(
                "INSERT INTO recurring (type,amount,currency,account_id,category_id,description,frequency,day_of_month,next_occurrence,total_installments,installments_fired,raw_message_id,user_id) "
                "VALUES (?,?,?,?,?,?,'monthly',?,?,?,?,?,?)",
                ("gasto", per_cuota, op.get("currency","ARS"), acc["id"],
                 cat["id"] if cat else None, op.get("description","Compra en cuotas"),
                 day, next_occ, n, cuota_actual,
                 op.get("raw_id"), op["user_id"]))
            rid = cur.lastrowid

            occurred_at = now_local().strftime("%Y-%m-%dT%H:%M")
            desc_full = f"{op.get('description','Compra en cuotas')} (cuota {cuota_actual}/{n})"
            cur2 = conn.execute(
                "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,recurring_id,user_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                ("gasto", per_cuota, op.get("currency","ARS"), acc["id"],
                 cat["id"] if cat else None, desc_full, occurred_at, rid, op["user_id"]))
            fired_tx_id = cur2.lastrowid

            if cuota_actual >= n:
                conn.execute("UPDATE recurring SET active=0 WHERE id=?", (rid,))
            conn.commit(); conn.close()

            extras = ""
            if cuota_actual > 1:
                extras = (f"\\n   <i>Cuotas 1-{cuota_actual-1} se asumen como ya pasadas "
                          f"en meses previos; no las cargo para evitar duplicar.</i>")
            restantes = max(0, n - cuota_actual)
            msg = (f"✅ Cargado.\\n"
                   f"   {interp}\\n"
                   f"   Cuota actual cargada: <b>{cuota_actual}/{n}</b> "
                   f"({restantes} restantes que se cobrarán solas mes a mes)."
                   f"{extras}\\n"
                   f"   Recurrente #{rid} · tx #{fired_tx_id}")
            await q.edit_message_text(base_text + "\\n\\n" + msg, parse_mode="HTML")
        except Exception as e:
            log.exception("phct save fail")
            await q.edit_message_text(base_text + f"\\n\\n❌ Error al guardar: {e}")
        return

'''


def main():
    src = MAIN.read_text(encoding="utf-8")
    if MARK in src:
        print("ya estaba parchado.")
        return

    # 1) Si quedó alguna rama phct vieja, removela
    if re.search(r'    # >>> photo cuotas v?\d?', src):
        src = re.sub(r'    # >>> photo cuotas v?\d?\n(?:    .*\n)+?(?=    if action == "txcancel")', "", src, count=1)
        print("  + rama phct vieja removida")

    # 2) Insertar la rama nueva justo ANTES de 'if action == "txcancel":' dentro del callback
    # Anchor robusto: buscar el primer 'if action == "txcancel":' (es unico)
    anchor = '    if action == "txcancel":'
    if anchor not in src:
        raise SystemExit("ERROR: no encontre 'if action == \"txcancel\":' en callback_handler.")
    src = src.replace(anchor, CALLBACK_BRANCH + anchor, 1)
    print("  + rama phct v2 insertada")

    # marca
    src = src.replace("anthropic_client = Anthropic", f"# {MARK}\nanthropic_client = Anthropic", 1)

    bk = MAIN.with_name(f"main.py.bak.phctfix.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(MAIN, bk)
    MAIN.write_text(src, encoding="utf-8")
    print(f"\n✅ main.py parchado (backup: {bk.name})")
    print("Reinicia: sudo systemctl restart asistente")


if __name__ == "__main__":
    main()
