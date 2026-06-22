"""
v5 — comportamiento consistente para TODAS las cuotas:
- Ninguna cuota se carga como transaccion el dia del registro.
- La proxima cuota a cobrar (sea la 1, 2, X) cae en la fecha de cierre
  de la tarjeta de credito.
- Las cuotas siguientes caen una por mes en cada cierre subsiguiente.

Esto reemplaza la logica de v3/v4 donde la cuota 1 se disparaba hoy.

Tambien arregla el Merpago que se cargó el 22/JUN (debería caer el 27/JUN).
Si querés "limpiar" la transaccion errónea de Merpago, despues de aplicar
este patch borrala manualmente con: /borrar <id>  (el id sale en /movimientos)

Uso:
    cd ~/asistente
    sudo systemctl stop asistente
    ~/asistente/venv/bin/python apply_photo_cuotas_v5.py
    sudo systemctl start asistente
"""

import re, shutil
from datetime import datetime
from pathlib import Path

MAIN = Path(__file__).parent / "main.py"
MARK = "# >>> photo cuotas v5"

CALLBACK_BRANCH = '''    # >>> photo cuotas v5
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
                    base_text + f"\\n\\n❌ No tengo la cuenta '{op.get('account','')}' creada. "
                    f"Creala con /addcuenta y volvé a mandar la foto.")
                return
            cat = get_category_by_name(op.get("category","Otros"))

            # next_occurrence = proximo cierre de la tarjeta
            closing_day = acc.get("closing_day")
            day = closing_day if closing_day else now_local().day
            try:
                import vencimientos as _v
                if closing_day:
                    _next = _v.proxima_fecha_para_cuota(closing_day, now_local().date())
                    next_occ_str = _next.strftime("%Y-%m-%d")
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
                explain = (f"   Cuota <b>1/{n}</b> es la próxima — cae el <b>{next_occ_str}</b> (cierre de la tarjeta).\\n"
                           f"   Quedan {restantes} cuotas en total ({restantes-1} más después).")
            else:
                explain = (f"   Cuotas 1 a {cuota_actual-1}: asumidas como ya pagadas en meses anteriores.\\n"
                           f"   Cuota <b>{cuota_actual}/{n}</b> es la próxima — cae el <b>{next_occ_str}</b>.\\n"
                           f"   Quedan {restantes} cuotas por delante.")

            msg = (f"✅ Cargado como recurrente.\\n"
                   f"   {interp}\\n"
                   f"{explain}\\n"
                   f"   Recurrente #{rid}")
            await q.edit_message_text(base_text + "\\n\\n" + msg, parse_mode="HTML")
        except Exception as e:
            log.exception("phct save fail")
            await q.edit_message_text(base_text + f"\\n\\n❌ Error al guardar: {e}")
        return

'''


def main():
    if not MAIN.exists():
        raise SystemExit("ERROR: no encuentro main.py")
    src = MAIN.read_text(encoding="utf-8")
    if MARK in src:
        print("ya estaba parchado v5.")
        return

    # 1) Remover branch phct anterior (cualquier version)
    pat_old = re.compile(
        r'    # >>> photo cuotas v?\d*\s*\n    if action == "phct":[\s\S]*?\n        return\n+',
        re.DOTALL,
    )
    if pat_old.search(src):
        src = pat_old.sub("", src, count=1)
        print("  + branch phct viejo removido")
    else:
        pat_old2 = re.compile(
            r'\n    if action == "phct":[\s\S]*?\n        return\n+',
            re.DOTALL,
        )
        if pat_old2.search(src):
            src = pat_old2.sub("\n", src, count=1)
            print("  + branch phct viejo (sin marca) removido")

    # 2) Insertar el branch v5
    anchor = '    if action == "txcancel":'
    if anchor not in src:
        raise SystemExit("ERROR: no encontre 'if action == \"txcancel\":' en callback_handler.")
    src = src.replace(anchor, CALLBACK_BRANCH + anchor, 1)
    print("  + branch phct v5 insertado")

    # marca
    if "anthropic_client = Anthropic" in src:
        src = src.replace("anthropic_client = Anthropic", f"# {MARK}\nanthropic_client = Anthropic", 1)

    bk = MAIN.with_name(f"main.py.bak.phctv5.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(MAIN, bk)
    MAIN.write_text(src, encoding="utf-8")
    print(f"\n✅ main.py parchado (backup: {bk.name})")
    print("Reinicia: sudo systemctl restart asistente")


if __name__ == "__main__":
    main()
