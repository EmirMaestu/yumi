# Proactividad de Yumi en WhatsApp (vía oficial / Cloud API) — spec

**Fecha:** 2026-07-10 · **Estado:** aprobado (modelo + decisiones confirmados por el dueño)

Objetivo: que Yumi entregue **recordatorios y avisos** por **WhatsApp** (además de Telegram), usando la **WhatsApp Cloud API oficial de Meta**, minimizando costo gracias a la ventana de servicio de 24h y cumpliendo términos (sin riesgo de baneo del número compartido).

## Contexto / decisión de fondo
- Se evaluó **OpenWA** (gateway self-hosted sobre `whatsapp-web.js`/`baileys` — automatización **no oficial** de WhatsApp Web). Permite proactividad gratis pero **viola los términos de Meta** y el baneo es real y sin aviso. Como Yumi usa **un solo número de producción para todos** los usuarios, un baneo = **caída total** de WhatsApp para todos los que pagan → **descartado para el producto**.
- Se eligió la **vía oficial**. La simulación de costos lo respalda: los "utility" son **gratis dentro de la ventana de 24h**; fuera de ventana Argentina = **US$0,026/msg**. Para las primeras decenas de usuarios el costo mensual es de pocos dólares (ver Anexo). EE.UU. = US$0,004 (relevante si se apunta a talleres US / MotorMec).

## Decisiones confirmadas
- **La ventana de 24h decide el modo automáticamente:** usuario escribió hace <24h → **texto libre**; callado >24h → **plantilla de utilidad**.
- **El disparo vive en el bot** (el `reminder_watchdog` que ya corre cada 60s), no en un scheduler nuevo del proceso web.
- **Alcance de este spec: solo recordatorios/avisos.** Digest semanal, alertas de dólar y otros proactivos quedan **fuera** (siguiente iteración, reusan la misma pieza).

## Modelo de datos (aditivo)
- `users.wa_last_inbound_at TEXT` — timestamp del último mensaje ENTRANTE de WhatsApp del usuario. Migración idempotente en el init de `main.py` (patrón `_ensure` existente).
- `users.notify_channel TEXT DEFAULT NULL` — preferencia de canal para proactividad: `NULL`/`auto` (resolver por lo que tenga), `telegram`, `whatsapp`, `both`. Sin UI en este spec (se setea a mano para testear); el toggle en "Yo" es follow-up.

## Componentes
1. **`wa_send_template(to, template_name, params, lang="es_AR")`** (nuevo, en `web.py` junto a `wa_send`). POST a `/{PHONE_NUMBER_ID}/messages` con `type:"template"`, `template.name`, `template.language.code`, y `components` con los `body` params. Mismo token/manejo de error que `wa_send`. Fail-safe (loguea, no rompe).
2. **Ventana abierta** — helper `wa_window_open(user_row)` = `now − wa_last_inbound_at < 24h` (usa `wa_last_inbound_at`).
3. **Registrar entrante** — en el **webhook de WhatsApp** (donde ya se procesa cada inbound), setear `wa_last_inbound_at = now` para el usuario. Un solo `UPDATE`.
4. **Router de entrega `notify_user(conn, user_row, text, template_key="yumi_aviso", template_params=None)`** (en `main.py`, reutilizable por watchdog y futuros proactivos):
   - Resuelve canal(es) según `notify_channel` (auto: Telegram si `telegram_id` real; WhatsApp si `wa_id`; si linked y sin preferencia → Telegram por default).
   - **Telegram:** `bot.send_message(telegram_id, text)` (como hoy).
   - **WhatsApp:** si `wa_window_open` → `wa_send(wa_id, text)`; si no → `wa_send_template(wa_id, "yumi_aviso", [text])`.
   - `telegram_id` negativo (placeholder WhatsApp-only) → NO se usa para Telegram (evita el fallo actual).

## Regla libre vs plantilla (núcleo)
```
entregar_wa(wa_id, texto):
  si (now - wa_last_inbound_at) < 24h:  wa_send(wa_id, texto)             # gratis, texto libre
  si no:                                 wa_send_template(wa_id, "yumi_aviso", [texto])   # utility, US$0.026
```

## Plantillas a aprobar (mínimas)
- **`yumi_aviso`** (categoría **Utility**, idioma `es_AR`) — cuerpo: `⏰ {{1}}`. Cubre recordatorios y avisos con una sola plantilla (el contenido va en la variable).
- Se aprueban una vez en Meta; después no hay aprobación por mensaje.

## Integración en el `reminder_watchdog`
Hoy arma `chat_id = owner_tg` y hace `context.bot.send_message`. Se cambia por `notify_user(conn, user_row, "⏰ "+r['text'])` para que enrute Telegram/WhatsApp. **Efecto colateral positivo:** arregla el bug conocido de que los recordatorios de usuarios **WhatsApp-only nunca se entregaban**.

## Setup una sola vez (lo hace el dueño en Meta) — checklist
1. **Business Verification** en Meta Business Manager (sube el límite de conversaciones iniciadas por el negocio; sin verificar el tope es bajo — ~250/24h).
2. **Crear y enviar a aprobar** la plantilla `yumi_aviso` (Utility, es_AR, cuerpo `⏰ {{1}}`).
3. **Confirmar método de pago** en la WABA (necesario para mensajes fuera de ventana).
4. Verificar que la WABA sigue **suscrita a la app** (`/subscribed_apps`) y el token del System User ve la WABA (ya resuelto antes).

## Testing (sin spamear)
- **Unit (pytest):** `wa_window_open` (abierta/cerrada) y que el router elige libre vs plantilla según `wa_last_inbound_at`. Mockear los `wa_send*` (no red).
- **Real controlado:** enviar a **el número propio del dueño**, un caso dentro de ventana (texto libre) y uno fuera (plantilla), antes de tocar a cualquier otro usuario.
- Nada masivo hasta validar ambos modos en vivo.

## Fuera de alcance (follow-ups)
- Digest semanal / vencimientos / alertas de dólar por WhatsApp (reusan `notify_user`).
- Toggle de canal en "Yo".
- Manejo de opt-out ("STOP") — buena práctica, no bloqueante para utility a baja escala.

## Riesgos / consideraciones
- **Límite de conversaciones iniciadas** sin Business Verification (~250/24h) — suficiente para beta; verificar antes de escalar.
- **Rechazo de plantilla** — el cuerpo `⏰ {{1}}` es genérico; si Meta lo rechaza por muy vago, agregar contexto fijo (ej. `Recordatorio de Yumi: {{1}}`).
- **Costo** — controlado por diseño (solo fuera de ventana). Monitorear con un contador simple si se quiere (follow-up).

## Criterios de aceptación
- Un recordatorio a un usuario de WhatsApp llega: texto libre si escribió <24h, plantilla si no.
- Los usuarios de Telegram siguen recibiendo igual que hoy.
- Los recordatorios de usuarios WhatsApp-only ahora **sí** se entregan.
- Sin envíos fuera de la ventana que no sean plantilla (no se cae ningún mensaje por regla de Meta).
- Tests de la regla libre/plantilla en verde.

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
