"""
v3 del flujo de fotos en cuotas. Arregla DOS cosas:

1. (de v2) El v2 anterior fallo al insertar el branch phct en callback_handler;
   este patcher lo inserta de forma robusta usando un anchor menos fragil.

2. (logica nueva) Cuando la foto muestra "Cuota X/N":
   - Cuotas 1..X-1: se asumen ya pagadas en meses anteriores (no se crean tx).
   - Cuota X: es la PROXIMA a cobrar; NO se crea transaccion hoy, se programa
     para que el daily-job la cargue en la fecha de cierre de la tarjeta.
   - Cuotas X+1..N: caen solas mes a mes en cada cierre.
   - Si X == 1 (compra nueva): cuota 1 SI se crea como tx hoy.

Tambien recalcula next_occurrence usando el closing_day de la cuenta
(via el modulo vencimientos.py) — si la cuenta no tiene cierre setteado,
cae a un fallback de un mes desde hoy.

Es seguro de aplicar varias veces: detecta el branch viejo y lo reemplaza.

Uso:
    cd ~/asistente
    sudo systemctl stop asistente
    ~/asistente/venv/bin/python apply_photo_cuotas_v3.py
    sudo systemctl start asistente
"""

import re, shutil
from datetime import datetime
from pathlib import Path

MAIN = Path(__file__).parent / "main.py"
MARK = "# >>> photo cuotas v3"

CALLBACK_BRANCH = '''    # >>> photo cuotas v3
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

            # next_occurrence = proximo cierre de la tarjeta (si tiene closing_day)
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

            conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row

            if cuota_actual == 1:
                # Nueva compra: cuota 1 se carga hoy, las siguientes mes a mes.
                cur = conn.execute(
                    "INSERT INTO recurring (type,amount,currency,account_id,category_id,description,frequency,day_of_month,next_occurrence,total_installments,installments_fired,raw_message_id,user_id) "
                    "VALUES (?,?,?,?,?,?,'monthly',?,?,?,?,?,?)",
                    ("gasto", per_cuota, op.get("currency","ARS"), acc["id"],
                     cat["id"] if cat else None, op.get("description","Compra en cuotas"),
                     day, next_occ_str, n, 1,
                     op.get("raw_id"), op["user_id"]))
                rid = cur.lastrowid
                occurred_at = now_local().strftime("%Y-%m-%dT%H:%M")
                desc_full = f"{op.get('description','Compra en cuotas')} (cuota 1/{n})"
                cur2 = conn.execute(
                    "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,recurring_id,user_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    ("gasto", per_cuota, op.get("currency","ARS"), acc["id"],
                     cat["id"] if cat else None, desc_full, occurred_at, rid, op["user_id"]))
                fired_tx_id = cur2.lastrowid
                if n == 1:
                    conn.execute("UPDATE recurring SET active=0 WHERE id=?", (rid,))
                conn.commit(); conn.close()
                msg = (f"✅ Cargado.\\n"
                       f"   {interp}\\n"
                       f"   Cuota <b>1/{n}</b> cargada hoy.\\n"
                       f"   Próxima cuota (2/{n}) cae automáticamente el <b>{next_occ_str}</b>.\\n"
                       f"   Recurrente #{rid} · tx #{fired_tx_id}")
            else:
                # cuota_actual > 1: cuotas 1..X-1 ya pasaron en meses previos.
                # NO creamos transaccion hoy: la cuota X es la próxima, va a caer
                # automaticamente cuando llegue next_occurrence (cierre de la tarjeta).
                cur = conn.execute(
                    "INSERT INTO recurring (type,amount,currency,account_id,category_id,description,frequency,day_of_month,next_occurrence,total_installments,installments_fired,raw_message_id,user_id) "
                    "VALUES (?,?,?,?,?,?,'monthly',?,?,?,?,?,?)",
                    ("gasto", per_cuota, op.get("currency","ARS"), acc["id"],
                     cat["id"] if cat else None, op.get("description","Compra en cuotas"),
                     day, next_occ_str, n, cuota_actual - 1,
                     op.get("raw_id"), op["user_id"]))
                rid = cur.lastrowid
                conn.commit(); conn.close()
                restantes = n - (cuota_actual - 1)
                msg = (f"✅ Cargado.\\n"
                       f"   {interp}\\n"
                       f"   Cuotas 1 a {cuota_actual-1}: asumidas como ya pagadas en meses anteriores.\\n"
                       f"   Cuota <b>{cuota_actual}/{n}</b> es la próxima — va a aparecer el <b>{next_occ_str}</b>.\\n"
                       f"   Quedan {restantes} cuotas por delante (la próxima + {restantes-1} más).\\n"
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
        print("ya estaba parchado v3.")
        return

    # 1) Remover cualquier branch phct anterior (v1 o v2).
    # Patron: linea con "# >>> photo cuotas" (cualquier version) seguida del bloque
    # "if action == \"phct\":..." hasta que aparezca el siguiente "if action ==" o doble newline.
    removed = False
    pat_old = re.compile(
        r'    # >>> photo cuotas v?\d*\s*\n    if action == "phct":[\s\S]*?\n        return\n+',
        re.DOTALL,
    )
    if pat_old.search(src):
        src = pat_old.sub("", src, count=1)
        removed = True
        print("  + branch phct viejo removido")
    else:
        # buscar solo el bloque "if action == \"phct\":" sin la marca de comentario
        pat_old2 = re.compile(
            r'\n    if action == "phct":[\s\S]*?\n        return\n+',
            re.DOTALL,
        )
        if pat_old2.search(src):
            src = pat_old2.sub("\n", src, count=1)
            removed = True
            print("  + branch phct viejo (sin marca) removido")

    if not removed:
        print("  · no habia branch phct previo, OK")

    # 2) Insertar el branch v3 justo antes de 'if action == "txcancel":'
    anchor = '    if action == "txcancel":'
    if anchor not in src:
        raise SystemExit("ERROR: no encontre 'if action == \"txcancel\":' en callback_handler.")
    src = src.replace(anchor, CALLBACK_BRANCH + anchor, 1)
    print("  + branch phct v3 insertado")

    # marca
    if "anthropic_client = Anthropic" in src:
        src = src.replace("anthropic_client = Anthropic", f"# {MARK}\nanthropic_client = Anthropic", 1)

    bk = MAIN.with_name(f"main.py.bak.phctv3.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(MAIN, bk)
    MAIN.write_text(src, encoding="utf-8")
    print(f"\n✅ main.py parchado (backup: {bk.name})")
    print("Reinicia: sudo systemctl restart asistente")


if __name__ == "__main__":
    main()
