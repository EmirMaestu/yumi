"""
v4 — actualiza PHOTO_TEMPLATE y handle_photo para que la vision detecte
MULTIPLES compras en cuotas en una sola imagen (no solo la primera).

El v3 anterior solo cambio el callback_handler; el prompt y el handler
quedaron en v1 (que solo soportaban una cuota por imagen).

Este patcher es independiente del v3 (no toca el callback).
Es idempotente.

Uso:
    cd ~/asistente
    sudo systemctl stop asistente
    ~/asistente/venv/bin/python apply_photo_cuotas_v4.py
    sudo systemctl start asistente
"""

import re, shutil
from datetime import datetime
from pathlib import Path

MAIN = Path(__file__).parent / "main.py"
MARK = "# >>> photo cuotas v4"

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

INCLUI tanto los consumos NUEVOS del periodo (ej: "Consumos del 28/MAY al 27/JUN")
como los de "Cuotas de consumos anteriores" (compras viejas que siguen activas).
Cada una es un item independiente en el array "cuotas_detectadas".

Si la cuota_actual es > 1, eso significa que la compra es vieja y ya cobraron
cuotas previas (cuota_actual - 1 cuotas ya pasaron). Igual devolve el item;
el bot maneja eso.

CADA cuota detectada debe ser un objeto del array. Si la imagen muestra 2
compras en cuotas (una nueva + una vieja), devolves DOS objetos. Si muestra 5,
devolves CINCO. Es CRITICO no fusionar items ni omitir ninguno.

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
    transacciones:[]  y cuotas_detectadas:[todos los items en cuotas, uno por cada]
- Si la imagen es un ticket/comprobante UNICO sin cuotas:
    transacciones:[un item]  y cuotas_detectadas:[]
- Si la imagen tiene un ticket con N cuotas (un solo item con monto+cuotas):
    transacciones:[]  y cuotas_detectadas:[ese item]
- Si la imagen tiene una lista mixta (algunos en cuotas, otros no):
    transacciones:[los que NO son en cuotas]  y cuotas_detectadas:[los que SI]

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

    # Normalizar cuotas_detectadas a lista
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
                  f"Te pregunto una por una qué hacer con cada una.") if len(cds) > 1 else \\
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
            anterior = " · es una cuota ya en curso" if cuota_actual > 1 else ""
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
            await update.message.reply_text(
                f"Y además detecté {len(txs)} transacción(es) sin cuotas. Las cargo abajo:")
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
        try: await notice.delete()
        except Exception: pass'''


def main():
    if not MAIN.exists():
        raise SystemExit("ERROR: no encuentro main.py")
    src = MAIN.read_text(encoding="utf-8")
    if MARK in src:
        print("ya estaba parchado v4.")
        return

    # 1) Reemplazar PHOTO_TEMPLATE
    pat = re.compile(r'PHOTO_TEMPLATE\s*=\s*"""[\s\S]*?"""', re.DOTALL)
    m = pat.search(src)
    if not m:
        raise SystemExit("ERROR: no encontre PHOTO_TEMPLATE")
    src = src[:m.start()] + PHOTO_TEMPLATE_NEW + src[m.end():]
    print("  + PHOTO_TEMPLATE v4 (multi-cuotas)")

    # 2) Reemplazar handle_photo
    pat2 = re.compile(
        r'async def handle_photo\(update, context\):.*?(?=\n\nasync def reminder_watchdog)',
        re.DOTALL,
    )
    m2 = pat2.search(src)
    if not m2:
        raise SystemExit("ERROR: no encontre handle_photo")
    src = src[:m2.start()] + HANDLE_PHOTO_NEW + src[m2.end():]
    print("  + handle_photo v4 (itera array)")

    # marca
    if "anthropic_client = Anthropic" in src:
        src = src.replace("anthropic_client = Anthropic", f"# {MARK}\nanthropic_client = Anthropic", 1)

    bk = MAIN.with_name(f"main.py.bak.phctv4.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(MAIN, bk)
    MAIN.write_text(src, encoding="utf-8")
    print(f"\n✅ main.py parchado (backup: {bk.name})")
    print("Reinicia: sudo systemctl restart asistente")


if __name__ == "__main__":
    main()
