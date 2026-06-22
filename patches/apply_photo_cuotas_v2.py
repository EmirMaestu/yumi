"""
v2 del detector de cuotas en fotos:
- Detecta MULTIPLES cuotas en una sola imagen (ej: resumen Naranja con
  "consumo del mes" + "cuotas de consumos anteriores").
- Para cada una pregunta total/cuota/saltar.
- Si la cuota actual es > 1 (compra vieja que sigue corriendo), arma
  el recurrente con installments_fired = cuota_actual y NO crea cuotas
  duplicadas.

Sobre-escribe el patch v1 si ya estaba aplicado.

Uso:
    cd ~/asistente
    sudo systemctl stop asistente
    ~/asistente/venv/bin/python apply_photo_cuotas_v2.py
    sudo systemctl start asistente
"""

import re, shutil
from datetime import datetime
from pathlib import Path

MAIN = Path(__file__).parent / "main.py"
MARK = "# >>> photo cuotas v2"

PHOTO_TEMPLATE_NEW = '''PHOTO_TEMPLATE = """Eres un parser de comprobantes en espanol rioplatense.
Recibis una imagen (ticket, factura, captura de MercadoPago/banco/Naranja/Visa, etc) y extraes transacciones.

CUENTAS DE __ME__ (elegi UNA por transaccion/cuota, exacta):
__ACCOUNTS__

CATEGORIAS:
__CATEGORIES__

══ DETECCION DE CUOTAS (CRITICO) ══
Tu trabajo principal es identificar TODOS los consumos en cuotas visibles en la imagen.

Considera "compra en cuotas" cualquier linea/tarjeta que muestre:
  - "Cuota X/N"  (ej: Cuota 1/6, Cuota 2/9)
  - "X de N cuotas"
  - "Plan en N cuotas"
  - "Cuota X/N" en una columna aparte

INCLUI tanto los consumos NUEVOS del periodo como los de "Cuotas de consumos anteriores"
(las que vienen de meses previos pero siguen activas). Cada una es un item independiente
en el array "cuotas_detectadas".

Si la cuota_actual es > 1, eso significa que la compra es vieja y ya cobraron cuotas
previas (cuota_actual - 1 cuotas ya pasaron). Igual devolve el item; el bot maneja eso.

══ Formato de salida EXCLUSIVO ══
{
  "transacciones": [
    {"type":"gasto"|"ingreso","amount":number,"currency":"ARS"|"USD"|"EUR",
     "category":string,"account":string,"description":string,
     "occurred_at":"YYYY-MM-DDTHH:MM"}
  ],
  "cuotas_detectadas": [
    {"amount":number,"cuotas_total":number,"cuota_actual":number,
     "description":string,"account":string,"category":string,
     "currency":"ARS"|"USD"|"EUR","occurred_at":"YYYY-MM-DDTHH:MM"}
  ]
}

REGLAS de uso de los campos:
- Si la imagen muestra SOLO consumos en cuotas (resumen de tarjeta tipo Naranja):
    transacciones:[]  y cuotas_detectadas: [todos los items en cuotas]
- Si la imagen es un ticket/comprobante UNICO sin cuotas:
    transacciones: [un item]  y cuotas_detectadas: []
- Si la imagen tiene ambos (ticket con N cuotas mostrando un solo item con monto+cuotas):
    transacciones:[]  y cuotas_detectadas: [ese item]
- Si la imagen tiene una lista de consumos donde algunos son en cuotas y otros no:
    transacciones: [los que NO son en cuotas]  y cuotas_detectadas: [los que SI]

══ Reglas generales ══
- ARS por default. account: priorizar caption del usuario; sino deducir del header/logo.
- amount: el numero tal como aparece, sin asumir si es total o por cuota — el usuario lo aclara despues.
- description: comercio/concepto limpio, max 50 chars. Para "Merpago isaiasemirmaestu" o similar, dejalo asi (es identificador).
- INVERSIONES: oro, bonos, cripto, FCI, ETF, Bonar, AL30, GD30 -> account="Inversiones" si existe.
- occurred_at: fecha del consumo si la ves; sino __TODAY__T12:00.
- Si no detectas nada usable: ambos arrays vacios.
- UN solo JSON, sin texto extra alrededor."""'''


HANDLE_PHOTO_NEW = '''async def handle_photo(update, context):
    if not is_allowed(update): return
    photo = update.message.photo[-1]
    caption = (update.message.caption or "").strip()
    notice = await update.message.reply_text("📸 Analizando imagen...")
    img_path = PHOTO_DIR / f"{photo.file_id}.jpg"
    user_db = current_user(update)
    try:
        file = await context.bot.get_file(photo.file_id)
        await file.download_to_drive(img_path)
        with open(img_path, "rb") as f: image_bytes = f.read()
        parsed = parse_photo(image_bytes, caption,
                             user_id=user_db["id"] if user_db else None,
                             user_name=user_db["name"] if user_db else None)
    except Exception as e:
        log.exception("Photo error"); await notice.edit_text(f"Fallo el analisis 😕\\n({e})"); return
    finally:
        try: img_path.unlink()
        except Exception: pass

    user = update.effective_user
    raw_id = save_raw(user.id, user.username, "photo",
                      json.dumps({"caption":caption,"parsed":parsed}, ensure_ascii=False))

    # ─── Normalizar cuotas_detectadas a array ────────────────────────────
    cds = parsed.get("cuotas_detectadas") if isinstance(parsed, dict) else None
    if isinstance(cds, dict): cds = [cds]
    if not isinstance(cds, list): cds = []
    cds = [c for c in cds if c and c.get("amount") and int(c.get("cuotas_total", 0) or 0) >= 2]

    txs = parsed.get("transacciones", []) if isinstance(parsed, dict) else []
    txs = [t for t in txs if t and t.get("amount")]

    if not cds and not txs:
        await notice.edit_text("No identifique transacciones en la imagen."); return

    # ─── Caso A: cuotas detectadas ────────────────────────────────────────
    if cds:
        try: await notice.delete()
        except Exception: pass

        header = (f"📸 Detecté {len(cds)} compra(s) en cuotas en la imagen.\\n"
                  f"Voy a preguntarte una por una qué hacer con cada una.") if len(cds) > 1 else \\
                 "📸 Detecté una compra en cuotas en la imagen."
        await update.message.reply_text(header)

        for i, cd in enumerate(cds, 1):
            amt = float(cd["amount"])
            n = int(cd["cuotas_total"])
            cuota_actual = max(1, int(cd.get("cuota_actual", 1) or 1))
            cur = cd.get("currency","ARS")
            desc = (cd.get("description") or "Compra en cuotas")[:80]
            acc = cd.get("account") or ""
            cat = cd.get("category") or "Otros"
            occ = cd.get("occurred_at") or now_local().strftime("%Y-%m-%dT12:00")

            op_id = make_op_id()
            PENDING_OPS[op_id] = {
                "kind": "photo_cuota",
                "amount": amt, "cuotas": n, "cuota_actual": cuota_actual,
                "currency": cur,
                "description": desc, "account": acc, "category": cat,
                "occurred_at": occ, "raw_id": raw_id,
                "user_id": user_db["id"] if user_db else None,
                "chat_id": user.id,
            }

            per = amt / n
            total = amt * n
            tag = f"[{i}/{len(cds)}] " if len(cds) > 1 else ""
            anterior = " · esta es una cuota ya en curso" if cuota_actual > 1 else ""
            msg = (f"{tag}💳 {acc or '(cuenta no detectada — confirmá despues)'}\\n"
                   f"📝 {desc}\\n"
                   f"🧾 cuota {cuota_actual}/{n}{anterior}\\n"
                   f"💵 ${amt:,.2f} {cur}\\n\\n"
                   f"¿Ese monto es el <b>TOTAL</b> o el de <b>CADA cuota</b>?\\n"
                   f"   • Si total → cada cuota ≈ <b>${per:,.2f}</b>\\n"
                   f"   • Si cada cuota → total ≈ <b>${total:,.2f}</b>")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Total ${amt:,.0f} ÷ {n}", callback_data=f"phct:total:{op_id}"),
                 InlineKeyboardButton(f"Cada cuota × {n}", callback_data=f"phct:cuota:{op_id}")],
                [InlineKeyboardButton("⏭ Saltar (ya esta cargada)", callback_data=f"phct:skip:{op_id}"),
                 InlineKeyboardButton("❌ Cancelar", callback_data=f"phct:cancel:{op_id}")],
            ])
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=kb)

    # ─── Caso B: transacciones normales (no en cuotas) ────────────────────
    if txs:
        if cds:
            note_msg = f"Y además detecté {len(txs)} transacción(es) sin cuotas. Las cargo abajo:"
            await update.message.reply_text(note_msg)
        saved = []
        for tx in txs:
            try:
                save_transaction(tx, raw_id, user_db["id"] if user_db else None)
                saved.append(tx)
            except Exception: log.exception("Error guardando tx de foto")
        if not saved:
            if not cds:
                await notice.edit_text("Detecte transacciones pero no pude guardarlas.")
            return
        if len(saved) == 1 and not cds:
            tx = saved[0]
            sign = "💸" if tx.get('type','gasto')=='gasto' else "💰"
            m = f"{sign} {tx['amount']:,.2f} {tx.get('currency','ARS')}"
            if tx.get('description'): m += f" — {tx['description']}"
            m += f"\\n📂 {tx['account']}"
            if tx.get('category'): m += f" · 🏷️ {tx['category']}"
            await notice.edit_text(m)
        else:
            m = f"📸 {len(saved)} transacciones cargadas:\\n\\n"
            for tx in saved:
                sign = "-" if tx.get('type','gasto')=='gasto' else "+"
                m += f"{sign}{tx['amount']:,.2f} {tx.get('currency','ARS')} — {tx.get('description','')}\\n   📂 {tx['account']}\\n"
            if cds:
                await update.message.reply_text(m)
            else:
                await notice.edit_text(m)
    else:
        # solo cuotas, no hay txs — borramos el notice si quedó
        try: await notice.delete()
        except Exception: pass'''


CALLBACK_PATCH = '''    # >>> photo cuotas v2
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
                    f"creada para vos. Creala con /addcuenta y volve a mandar la foto.")
                return
            cat = get_category_by_name(op.get("category","Otros"))

            conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
            day = now_local().day
            next_occ = compute_next_monthly(now_local().strftime("%Y-%m-%d"), day)

            # 1) Insertar el recurrente con installments_fired = cuota_actual.
            #    Las cuotas anteriores (1..cuota_actual-1) se asumen ya pasadas
            #    en meses previos y NO se crean transacciones para ellas.
            cur = conn.execute(
                "INSERT INTO recurring (type,amount,currency,account_id,category_id,description,frequency,day_of_month,next_occurrence,total_installments,installments_fired,raw_message_id,user_id) "
                "VALUES (?,?,?,?,?,?,'monthly',?,?,?,?,?,?)",
                ("gasto", per_cuota, op.get("currency","ARS"), acc["id"],
                 cat["id"] if cat else None, op.get("description","Compra en cuotas"),
                 day, next_occ, n, cuota_actual,
                 op.get("raw_id"), op["user_id"]))
            rid = cur.lastrowid

            # 2) Insertar la transaccion de la cuota actual.
            occurred_at = now_local().strftime("%Y-%m-%dT%H:%M")
            desc_full = f"{op.get('description','Compra en cuotas')} (cuota {cuota_actual}/{n})"
            cur2 = conn.execute(
                "INSERT INTO transactions (type,amount,currency,account_id,category_id,description,occurred_at,recurring_id,user_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                ("gasto", per_cuota, op.get("currency","ARS"), acc["id"],
                 cat["id"] if cat else None, desc_full, occurred_at, rid, op["user_id"]))
            fired_tx_id = cur2.lastrowid

            # 3) Si era la ultima cuota, desactivamos el recurrente.
            if cuota_actual >= n:
                conn.execute("UPDATE recurring SET active=0 WHERE id=?", (rid,))
            conn.commit(); conn.close()

            extras = ""
            if cuota_actual > 1:
                extras = (f"\\n   <i>Cuotas {1}-{cuota_actual-1} se asumen como ya pasadas "
                          f"en meses previos; no las cargo para evitar duplicar.</i>")
            restantes = max(0, n - cuota_actual)
            msg = (f"✅ Cargado.\\n"
                   f"   {interp}\\n"
                   f"   Cuota actual cargada: <b>{cuota_actual}/{n}</b> "
                   f"({restantes} restantes que se cobraran solas mes a mes)."
                   f"{extras}\\n"
                   f"   Recurrente #{rid} · tx #{fired_tx_id}")
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
        print("ya estaba parchado en v2.")
        return

    # 1) Reemplazar PHOTO_TEMPLATE entero
    pat = re.compile(r'PHOTO_TEMPLATE\s*=\s*"""[\s\S]*?"""', re.DOTALL)
    m = pat.search(src)
    if not m:
        raise SystemExit("ERROR: no encontre PHOTO_TEMPLATE")
    src = src[:m.start()] + PHOTO_TEMPLATE_NEW + src[m.end():]
    print("  + PHOTO_TEMPLATE v2")

    # 2) Reemplazar handle_photo
    pat2 = re.compile(
        r'async def handle_photo\(update, context\):.*?(?=\n\nasync def reminder_watchdog)',
        re.DOTALL,
    )
    m2 = pat2.search(src)
    if not m2:
        raise SystemExit("ERROR: no encontre handle_photo")
    src = src[:m2.start()] + HANDLE_PHOTO_NEW + src[m2.end():]
    print("  + handle_photo v2")

    # 3) Reemplazar el branch phct: en callback_handler.
    # Buscamos cualquier branch phct existente (v1) y lo sacamos.
    pat3 = re.compile(r'    # >>> photo cuotas patch.*?(?=\n    if action == "txcancel")', re.DOTALL)
    if pat3.search(src):
        src = pat3.sub("", src)
        print("  + branch phct v1 removido")

    needle = 'await q.answer()\n\n    if action == "txcancel":'
    if needle not in src:
        raise SystemExit("ERROR: no encontre anchor en callback_handler.")
    src = src.replace(needle, 'await q.answer()\n\n' + CALLBACK_PATCH + '\n    if action == "txcancel":', 1)
    print("  + branch phct v2 insertado")

    # marca
    src = src.replace("anthropic_client = Anthropic", f"# {MARK}\nanthropic_client = Anthropic", 1)

    bk = MAIN.with_name(f"main.py.bak.phct2.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(MAIN, bk)
    MAIN.write_text(src, encoding="utf-8")
    print(f"\n✅ main.py parchado (backup: {bk.name})")
    print("Reinicia: sudo systemctl restart asistente")


if __name__ == "__main__":
    main()
