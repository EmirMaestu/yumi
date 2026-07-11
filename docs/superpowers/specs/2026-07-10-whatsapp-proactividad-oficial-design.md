# Proactividad de Yumi en WhatsApp (vía oficial / Cloud API) — spec

**Fecha:** 2026-07-10 · **Estado:** aprobado (modelo + decisiones confirmados por el dueño)

Objetivo: que Yumi entregue **recordatorios y avisos** por **WhatsApp** (además de Telegram), usando la **WhatsApp Cloud API oficial de Meta**, minimizando costo gracias a la ventana de servicio de 24h y cumpliendo términos (sin riesgo de baneo del número compartido).

## Contexto / decisión de fondo
- Se evaluó **OpenWA** (gateway self-hosted sobre `whatsapp-web.js`/`baileys` — automatización **no oficial** de WhatsApp Web). Permite proactividad gratis pero **viola los términos de Meta** y el baneo es real y sin aviso. Como Yumi usa **un solo número de producción para todos** los usuarios, un baneo = **caída total** de WhatsApp para todos los que pagan → **descartado para el producto**.
- Se eligió la **vía oficial**. La simulación de costos lo respalda: los "utility" son **gratis dentro de la ventana de 24h**; fuera de ventana Argentina = **US$0,026/msg**. Para las primeras decenas de usuarios el costo mensual es de pocos dólares (ver Anexo). EE.UU. = US$0,004 (relevante si se apunta a talleres US / MotorMec).

## Decisiones confirmadas
- **La ventana de 24h decide el modo automáticamente:** usuario escribió hace <24h → **texto libre**; callado >24h → **plantilla de utilidad**.
- **El disparo vive en el bot** (el `reminder_watchdog` que ya corre cada 60s), no en un scheduler nuevo del proceso web.
- **Gate por plan (free vs pago):** el **plan free recibe WhatsApp proactivo SOLO dentro de la ventana de 24h** (texto libre, gratis); fuera de ventana no se manda plantilla (paga). Los planes de pago sí reciben plantilla fuera de ventana. Implementado con `allow_template` en `delivery_plan`/`notify_user`, calculado en el watchdog como `PLAN_RANK[household_plan(uid)] >= 1`.
- **In-window NO requiere setup de Meta:** el texto libre dentro de la ventana es un mensaje de servicio (lo inicia el usuario) → funciona con el número ya conectado, **sin plantilla/verificación/pago**. Por eso la proactividad del plan free se puede prender YA; el setup de Meta es solo para el caso fuera de ventana (plantilla, planes de pago).
- **Alcance de este spec: solo recordatorios/avisos.** Digest semanal, alertas de dólar, recurrentes generadas y otros proactivos quedan **fuera** (siguiente iteración, reusan la misma pieza).

## Modelo de datos (aditivo)
- `users.wa_last_inbound_at TEXT` — timestamp (UTC) del último mensaje ENTRANTE de WhatsApp del usuario. Migración idempotente en el bloque `_ALTERS` de `main.py`.
- `users.notify_channel TEXT` — preferencia de canal: `NULL`/`auto` (resolver por lo que tenga), `telegram`, `whatsapp`, `both`. Sin UI en este spec (se setea a mano para testear); el toggle en "Yo" es follow-up.

## Componentes
1. **`whatsapp_api.py`** (módulo compartido nuevo) — `send_text(to, text)` y `send_template(to, name, params, lang="es_AR")` vía Cloud API (urllib, fail-safe, credenciales del entorno). Lo usan web.py y main.py sin duplicar.
2. **`notify.py`** (módulo puro nuevo, sin deps pesadas → testeable en CI):
   - `wa_window_open(last_inbound_str, now_utc)` = `now − wa_last_inbound_at < 24h`.
   - `delivery_plan(user_row, now_utc)` → decide canal(es)+modo: `[('telegram',None)]` / `[('wa_text',None)]` / `[('wa_template','yumi_aviso')]`. `telegram_id` negativo = placeholder WhatsApp-only. `notify_channel=auto` con usuario linkeado (ambos) → prefiere Telegram (no duplica).
3. **`main.notify_user(bot, user_row, text, template_params, reply_markup)`** — ejecuta el `delivery_plan`: Telegram (`bot.send_message`), WhatsApp libre (`send_text`), o plantilla (`send_template`). Fail-safe por canal.
4. **Registrar entrante** — en el webhook de WhatsApp (`_wa_process_message`, tras resolver el usuario) se setea `wa_last_inbound_at = datetime('now')`.

## Regla libre vs plantilla (núcleo)
```
entregar_wa(wa_id, texto):
  si (now - wa_last_inbound_at) < 24h:  send_text(wa_id, texto)                        # gratis, texto libre
  si no:                                 send_template(wa_id, "yumi_aviso", [texto])    # utility, US$0.026
```

## Plantillas a aprobar (mínimas)
- **`yumi_aviso`** (categoría **Utility**, idioma `es_AR`) — cuerpo: `⏰ {{1}}`. Cubre recordatorios y avisos con una sola plantilla (el contenido va en la variable).
- Se aprueba una vez en Meta; después no hay aprobación por mensaje.

## Integración en el `reminder_watchdog`
La query suma `u.wa_id, u.wa_last_inbound_at, u.notify_channel`; el envío pasa de `context.bot.send_message(...)` a `notify_user(...)`, que enruta Telegram/WhatsApp. **Efecto colateral positivo:** arregla el bug conocido de que los recordatorios de usuarios **WhatsApp-only nunca se entregaban** (el `send_message` con telegram_id negativo fallaba). `send_reminder`/`recurring_daily` quedan como están (fuera de alcance).

## Setup una sola vez (lo hace el dueño en Meta) — checklist
1. **Business Verification** en Meta Business Manager (sube el límite de conversaciones iniciadas; sin verificar el tope es bajo — ~250/24h).
2. **Crear y enviar a aprobar** la plantilla `yumi_aviso` (Utility, es_AR, cuerpo `⏰ {{1}}`).
3. **Confirmar método de pago** en la WABA (necesario para mensajes fuera de ventana).
4. Verificar que la WABA sigue **suscrita a la app** (`/subscribed_apps`) y el token del System User ve la WABA (ya resuelto antes).

## Testing (sin spamear)
- **Unit (pytest, `tests/test_notify.py`):** `wa_window_open` (abierta/cerrada/borde/None/basura) y `delivery_plan` (todos los caminos: solo TG, WA-only ventana abierta/cerrada/nunca-escribió, linkeado auto→TG, pref both, pref whatsapp). Sin red.
- **Real controlado:** enviar a **el número propio del dueño**, un caso dentro de ventana (texto libre) y uno fuera (plantilla), antes de tocar a cualquier otro usuario.
- Nada masivo hasta validar ambos modos en vivo.

## Fuera de alcance (follow-ups)
- Digest semanal / vencimientos / alertas de dólar / recurrentes generadas por WhatsApp (reusan `notify_user`).
- Toggle de canal en "Yo".
- Manejo de opt-out ("STOP") — buena práctica, no bloqueante para utility a baja escala.

## Riesgos / consideraciones
- **Límite de conversaciones iniciadas** sin Business Verification (~250/24h) — suficiente para beta; verificar antes de escalar.
- **Rechazo de plantilla** — el cuerpo `⏰ {{1}}` es genérico; si Meta lo rechaza por vago, agregar contexto fijo (ej. `Recordatorio de Yumi: {{1}}`).
- **Costo** — controlado por diseño (solo fuera de ventana). Monitoreo con contador simple = follow-up.

## Criterios de aceptación
- Un recordatorio a un usuario de WhatsApp llega: texto libre si escribió <24h, plantilla si no.
- Los usuarios de Telegram siguen recibiendo igual que hoy.
- Los recordatorios de usuarios WhatsApp-only ahora **sí** se entregan.
- Sin envíos fuera de la ventana que no sean plantilla (no se cae ningún mensaje por regla de Meta).
- Tests de `wa_window_open`/`delivery_plan` en verde.

---

## Anexo — simulación de costos (justificación)
`costo mensual ≈ usuarios × (avisos fuera de ventana por usuario/día) × 30 × US$0,026` (≈ US$0,78 por "aviso-fuera-de-ventana/día").

| Avisos cobrables/usuario/día | Usuarios para US$20/mes | para US$30/mes |
|---|---|---|
| 0,25 | ~100 | ~155 |
| 0,5 | ~51 | ~77 |
| 1 | ~26 | ~38 |
| 2 | ~13 | ~19 |

Peor caso (todo fuera de ventana). En uso real la mayoría de los avisos caen dentro de las 24h → gratis. Precios: Meta pricing (Utility AR US$0,026, US US$0,004); a más volumen, Meta baja por tramos.
