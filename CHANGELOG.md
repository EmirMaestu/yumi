# Changelog

Todas las novedades relevantes de Yumi. Formato basado en [Keep a Changelog](https://keepachangelog.com/es/), versionado [SemVer](https://semver.org/lang/es/).

> Regla: cada tanda de features = bump de versión (MINOR), entrada en este archivo, tag de git (`vX.Y.Z`) y redeploy. `1.0.0` = lanzamiento del **asistente completo** (no solo finanzas).

## [Unreleased]
### Added
- **Calendario suscribible (.ics).** Cada usuario puede suscribir su Google/Apple/Outlook Calendar a un feed de Yumi y ver ahí sus **eventos + recordatorios** (los recordatorios con **alarma dentro del mismo evento**, no eventos sueltos). URL secreta y revocable, desde la pantalla **Agenda** ("Suscribir a mi calendario"). Una vía (Yumi → calendario, solo lectura), ventana de 30 días, zona horaria Buenos Aires. Backend: módulo `calfeed.py` (+ tests), endpoints `/api/cal/{url,regenerate,{token}.ics}`, columna `users.cal_token`, dep `icalendar`. Spec/plan en `docs/superpowers/`.
- **Recordatorios por WhatsApp: aviso "en desarrollo" + salidas.** Cuando un usuario de WhatsApp (sin Telegram vinculado) crea un recordatorio, el bot lo guarda y le ofrece **(a) "Agregar a mi calendario"**: un link a un `.ics` de **ese** recordatorio (un evento con su **alarma adentro**, no eventos sueltos) que el calendario del teléfono agrega en un toque y avisa solo a la hora; o **(b)** un **link de Telegram que vincula las cuentas al instante** (`t.me/<bot>?start=link_<código>`). Endpoint `GET /api/cal/{token}/rec/{rid}.ics`. Nuevo deep-link `link_` en `start_cmd` + `link_telegram_via_code` (vincula la cuenta de WhatsApp al telegram_id que abre el link).
- **Renombrar usuarios desde el panel admin** (botón ✏️ junto al nombre) — útil para los que entran por WhatsApp sin nombre de perfil (quedaban como "Usuario"). `PATCH /api/admin/users/{id}` ahora acepta `name`.

### Fixed
- **El bot frenaba a TODOS tras pocos mensajes (tope global).** El tope diario global era US$5 y una sola búsqueda de precios lo había superado (US$6.79) → el `cost_gate` bloqueaba a cualquiera ("llegamos al límite de hoy"), sin registrar su uso (de ahí "0 msj hoy") y **sin importar su plan** (por eso cambiar a "pareja" no destrababa). Se subió el tope a **US$15** (la búsqueda de precios ya está apagada, que era la causa) → destrabado.

### Added
- **Notificaciones push en la web (PWA).** La app instalada ahora puede recibir **notificaciones del navegador** (Web Push / VAPID, sin costo). Nuevo módulo `push_notify.py`, tabla `push_subscriptions`, endpoints `/api/push/{vapid-public-key,subscribe,unsubscribe,test}` y handlers `push`/`notificationclick` en el service worker. En iPhone requiere instalar la app primero (iOS 16.4+).
- **Avisos de vencimiento también por push.** El job diario que ya avisaba por **Telegram** los vencimientos de tarjeta y recurrentes (3 y 1 días antes, `payment_calendar_daily`) ahora **también manda push web** a quien lo tenga activado.
- **Banner "Instalá Yumi / Activá notificaciones"** en la home: botón real de instalar (Android/escritorio), instrucciones para iPhone, y activar notificaciones. Descartable. **Aclara que en iPhone la instalación es solo desde Safari** (no Brave/Chrome — iOS reserva "Agregar a inicio" a Safari). Guía completa en [docs/guia-instalar-app.md](docs/guia-instalar-app.md).

### Fixed
- **Vencimiento mal calculado en tarjetas con cierre temprano y vencimiento más tarde en el mes.** El cálculo asumía *siempre* "vencimiento = mes siguiente al cierre". Ahora: si el día de vencimiento es **mayor** al de cierre, vence el **mismo mes** (ej. cierre 2 / venc 13 → cierra 02/03, vence 13/03); si es menor o igual, el mes siguiente (ej. cierre 28 / venc 5). Centralizado en `_venc_para_cierre` (afecta `/vencimientos` y las cuotas). Se corrigieron las 7 cuotas de Santander/Amex que habían quedado un mes tarde.

### Changed
- **Búsqueda de precios online: interruptor para apagarla.** Es la función más cara del bot (web search + mucho texto). Nuevo flag `PRECIO_ENABLED` en el `.env` (default prendido). Apagada (`PRECIO_ENABLED=0`), el bot responde "temporalmente deshabilitada" en vez de buscar. El resumen semanal (`digest`, costo ~0) queda activo.

### Fixed
- **Las cuotas de tarjeta ahora caen en el VENCIMIENTO, no en el cierre.** Antes una cuota se "cobraba" el día de cierre de la tarjeta (ej. Naranja X cierre 27) cuando la plata recién sale en el vencimiento (~día 10). Ahora la cuota se programa y figura en "Hoy" en la fecha de vencimiento del resumen donde postea la compra (foto de cuotas + alta por texto). Si la tarjeta no tiene vencimiento cargado, se mantiene el cierre. **Se migraron las 9 cuotas activas** que estaban fechadas en el cierre. *(Requiere `due_day` en la tarjeta.)*
- **Doble conteo de recurrentes en el "a pagar" de tarjetas — corregido.** Las cuotas/suscripciones se contaban dos veces (como transacción del ciclo **y** como plan). Ahora el cálculo del ciclo (`calcular_vencimiento`) **excluye** las transacciones generadas por recurrentes (`recurring_id`), y las cuotas se cuentan una sola vez vía el plan — tal como el front ya asumía. Efecto: las cuotas pasan a verse en "ciclo en curso" y dejan de inflar "a pagar ahora".
- **Costos del admin: el gasto por persona no sumaba el total.** Las búsquedas de precio (`precio`, web search) y el resumen diario (`digest`) se registraban con `user_id` nulo → contaban en el "tope global" y "uso por modelo" pero en la tarjeta de nadie (este mes: US$6,65 de US$7,63 estaban sin asignar, 87%). Ahora se **atribuyen al usuario** que las dispara.

### Changed
- **Costo del web search acotado.** La búsqueda de precios pasó a **Haiku** (más barato), con **`max_uses: 3`** en la herramienta `web_search` y el loop de `pause_turn` limitado, para que una sola consulta no dispare la cuenta (una búsqueda llegó a costar **US$6,65 / ~2,1M tokens de entrada** en Sonnet).
- **La estimación de costo ahora incluye el cargo del `web_search`** (~US$10/1000 búsquedas, que va aparte de los tokens) para acercarse a la factura real de la API.
- **Panel admin → fila "Sistema (sin usuario)"** con el costo no atribuible (búsquedas/digest), para que *por-usuario + sistema = total*.

## [0.10.0] - 2026-06-27
### Security
- **Fuga de datos financieros entre hogares por el bot (CRÍTICA) — cerrada.** Las consultas del bot (`resolve_scope`/`build_consulta_filter`/`_eventos_query`/`_distinct_keyword_candidates`) resolvían `scope:"user:X"` y `"ours"`/"compartido" **sin chequear el hogar** → un usuario podía leer finanzas/eventos de otro (incluso por lenguaje natural: "cuánto gastó X"). Ahora `user:X` solo se permite si X es del mismo hogar y "compartido" se acota a `user_id IN (miembros del hogar)`. Verificado en vivo.
- **IDOR en los botones del bot (CRÍTICA) — cerrada.** Los callbacks (`tdone/tdel/txdel/rectoggle/recdel/remdel/lscheck/lsclear/cardpay`) borraban/modificaban por id **sin verificar dueño** → cualquier usuario podía destruir tareas/transacciones/recurrentes/recordatorios/items de compra de otro. Ahora todos filtran por `user_id IN (hogar)` (o el hogar dueño de la lista) y responden "No es tuya" si el id es ajeno.
- **Items compartidos editables entre hogares (ALTA) — cerrada.** En la web, marcar/borrar tareas y borrar notas con `shared=1` solo chequeaba la bandera, no el hogar → un atacante podía tocar un item compartido de **otro** hogar (y un `id` inexistente pasaba la guarda). Ahora la regla es **propio, o compartido y del mismo hogar** (`_can_touch_shared`), y un `id` ajeno/inexistente da 403. Misma corrección de raíz en `crud_v2.assert_ownership` (el `shared` solo aplica si el dueño es del hogar; `user_id NULL` huérfano ya no pasa).
- **Papelera y auditoría acotadas al hogar (MEDIA) — cerrada.** `list_trash`/`list_audit`/`restore`/`soft_delete` mostraban/operaban filas con `user_id IS NULL` (legacy/huérfanas) para cualquiera. Ahora todo se scopea a `user_id IN (miembros del hogar)`.
- **Modo "ambos" ya no agrega datos globales (MEDIA) — cerrada.** Las ramas de scope sin usuario fijo (`user_filter`/`user_filter_eq` y el listado de cuentas en la web) cuando el cookie decía "ambos"/"compartido" devolvían **todos** los registros sin filtro de usuario. Ahora se acotan a `user_id IN (miembros del hogar)`.
- **Hashing de contraseñas reforzado (ALTA).** Se pasó de **SHA-256 salteado de una vuelta** (rápido de crackear) a **PBKDF2-HMAC-SHA256, 200k iteraciones** (stdlib, sin dependencias). Compatibilidad hacia atrás: las claves viejas siguen validando y se **re-hashean a PBKDF2 automáticamente en el próximo login**. Comparación en tiempo constante (`secrets.compare_digest`).
- **Rate limiting en el login (ALTA).** `/login` ahora corta a **10 intentos por IP** y **6 por usuario** cada 5 min (HTTP 429) → frena fuerza bruta / credential stuffing. Limiter en memoria, por IP real (`X-Forwarded-For` detrás de Caddy).
- **Headers de seguridad HTTP (MEDIA).** Caddy ahora manda **HSTS, CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy, Permissions-Policy** y oculta el header `Server`. Mitiga clickjacking, sniffing y reduce superficie de XSS. *(Requiere aplicar el Caddyfile nuevo — ver DEPLOY.)*
- **IDOR en categorías (ALTA) — cerrada.** Las categorías de gastos eran **globales**: cualquier usuario logueado podía crear, renombrar o **borrar** las categorías de todos (`/api/categories` POST/PATCH/DELETE sin chequear dueño). Ahora son **por hogar**: las categorías default quedan compartidas (solo-lectura) y cada hogar ve/edita/borra **solo las suyas** (`household_id`; un id ajeno o una default → 403). Migración idempotente que reconstruye la tabla (quita el `UNIQUE` global de `name`, agrega `household_id`, índice `(household_id,name)`) **validada sobre copia de la base viva** (20→20 categorías, joins de transacciones intactos).
- **Credenciales fuera del repo.** `web-react/credenciales-whatsapp-yumi.txt` (tenía el App Secret en texto plano) quedó en `.gitignore` para que no se commitee. *(Pendiente del operador: rotar App Secret + token permanente de WhatsApp y mover el archivo a un gestor de contraseñas.)*

### Fixed
- **Los modales ya no se cierran al cambiar un Select.** El desplegable de Radix se portalea fuera del modal y el click se tomaba como "afuera" → se cerraba. Guard `onInteractOutside` en `Modal` y `Sheet` (QuickAdd).
- **Login más claro para quien llega por la web.** Explica que el usuario/clave los da el bot (Telegram/WhatsApp) y se cambian con `/password`, y agrega accesos directos al bot ("¿todavía no tenés cuenta? es por invitación") — antes era un form pelado sin salida.
- **Notas: el filtro "compartido" ya no cruza hogares** (se acota a miembros del hogar).

### Added
- **Renombrar cuentas desde el bot.** Nuevo intent `editar_cuenta`: «renombrá la cuenta Mercopal a Mercado Pago» ahora funciona (antes pedía un #ID que no existía).
- **Notas con descripción.** Además del título y las etiquetas, las notas tienen un campo de **descripción** (detalle más largo), editable en la web. Columna `notas.description`.
- **Vincular Telegram + WhatsApp en una sola cuenta.** Comando **`/vincular`** en Telegram genera un código de un solo uso (vence en 15 min); al mandarlo por WhatsApp (`vincular <código>`), ese WhatsApp queda enganchado a la misma cuenta (mismo `telegram_id` **y** `wa_id` en la fila) → ves lo mismo en los dos canales. Si había una cuenta de WhatsApp duplicada (creada al onboardear por separado), se fusiona/borra. Columnas nuevas `users.link_code`/`link_code_exp`.
- **Planes con límites reales (por hogar).** Cada plan define **cuántos integrantes** puede tener el hogar y **cuántos mensajes/día** por persona; el **mejor plan del hogar** manda (un miembro pago beneficia a toda la familia). Defaults (configurables por env): **free** = 1 integrante (solo) · 15 msj/día; **pareja** = 2 · 150 msj/día; **pro** = 6 · ~ilimitado. Se aplican en el bot: el `cost_gate` frena por la quota del plan del hogar, e **invitar a la familia** rechaza si el hogar ya llegó a su tope (`/invitar` avisa cuántos lugares quedan, o que el plan free no comparte).
- **Panel admin → Familias.** Nueva sección que muestra cada **hogar** con sus integrantes, el plan del hogar, ocupación (integrantes/tope) y mensajes/día. Endpoint `GET /api/admin/households`.
- **Invitar a la familia.** Cada usuario puede sumar a su familia a su **mismo hogar** (comparten listas, gastos y agenda) con el comando **`/invitar`** (alias `/familia`), que le da su link personal `t.me/<bot>?start=fam_<código>`. Quien lo abre se **une a ese hogar** (sin tope de 2 — es familia, no solo pareja). En WhatsApp funciona igual vía `wa.me/...fam_<código>`. Onboarding por referido (link de admin) sigue creando un **hogar nuevo**; el de familia **une al hogar existente**. *(Limitación: si el invitado ya tiene cuenta propia, no se fusiona automáticamente — recibe su bienvenida normal.)*
- **La bienvenida ahora dice cuál es la app web** (`APP_URL`, configurable) además del usuario y la clave temporal, y aclara que el bot también funciona en el chat.

### Security
- **Aislamiento de datos por hogar (multi-inquilino).** La app estaba construida como **un solo hogar compartido** (Emir + Lisa comparten todo). Al sumar el alta por referidos, un usuario nuevo quedaba dentro de ese hogar y **veía datos ajenos** (se detectó con las listas de compras). Ahora cada usuario tiene un **`household_id`**: la pareja comparte el hogar 1; **cada usuario nuevo queda solo en su propio hogar, totalmente aislado.** Se scopearon por hogar: listas de compras y plantillas (bot + web), resumen "compartido", `/compartido`, tareas y notas compartidas (bot), y el resolver de scope de la web (`resolve_scope_uid` + selector "ver datos de" en `/api/me`) — un usuario nuevo solo puede ver lo suyo y no puede seleccionar a otra persona. *(El modo "ambos" que antes agregaba global ya se acotó a miembros del hogar — ver arriba.)*

### Fixed
- **Inicio tardaba ~10s en cargar (request `overview2`).** El endpoint hacía una llamada **sincrónica** a la API del dólar (`dolarapi.com`) en el camino del request; con la **caché de DNS fría** (tras cada reinicio), la resolución de `getaddrinfo` tardaba ~9s y **no estaba acotada por el timeout del socket**, colgando toda la respuesta (confirmado con instrumentación: 9.28s, todos dentro de la llamada al dólar). Ahora la cotización se trae en un **hilo de fondo** que mantiene la caché tibia y se refresca cada 10 min; `get_dolar_rate` devuelve el valor cacheado al instante y **nunca bloquea** el request. El Inicio carga inmediato.

## [0.9.0] - 2026-06-25
### Added
- **WhatsApp (Meta Cloud API) — integración base (texto).** Yumi ahora también atiende por WhatsApp:
  webhook en `/api/whatsapp/webhook` (verificación + firma `X-Hub-Signature-256` con el App Secret),
  **onboarding por `wa.me`** (el primer mensaje trae el código de referido → da de alta al usuario),
  y **reutiliza el cerebro del bot** (parse + acciones) vía un *shim* que rutea las respuestas a WhatsApp.
  Mismo flujo de referidos que Telegram. El panel admin → Referidos ahora muestra **link de WhatsApp y de Telegram**.
- Usuarios de WhatsApp: se guardan con `telegram_id = -<teléfono>` (negativo, sin colisión) + nueva columna `wa_id`,
  para que toda la lógica existente (que indexa por `telegram_id`) funcione sin cambios.

### Pendiente (próximo incremento WhatsApp)
- **Audio** (notas de voz → Whisper, igual que Telegram).
- **Disparo de recordatorios/proactivos a WhatsApp** (hoy el watchdog envía solo por Telegram).
- Número de producción + verificación del negocio (el de prueba solo habla con destinatarios allow-listed).

## [0.8.0] - 2026-06-25
### Added
- **Onboarding por invitación + referidos (beta cerrada).** Yumi deja de ser whitelist fija: ahora
  "permitido" = **usuario registrado**. Entran **solo por link de referido** (`t.me/<bot>?start=<código>`):
  el bot da de alta al nuevo (crea su acceso web con clave temporal) y guarda **quién lo invitó**.
  Quien escribe sin invitación recibe un mensaje "Yumi es por invitación".
  - Solo **admins** reparten links durante la beta (configurable con `INVITE_MODE=all`).
  - Onboarding **channel-agnostic** (Telegram ya; WhatsApp en la próxima tanda, mismo flujo con `wa.me`).
  - **Panel admin → Referidos:** tu link copiable + "quién invitó a quién" + conteo por persona.

### Backend
- `users`: nuevas columnas `referral_code` (única, backfill para todos), `referred_by`, `channel`.
- `main.py`: helpers `gen_referral_code` / `get_user_by_referral_code` / `can_invite` / `onboard_user`;
  `is_allowed` pasa a "¿registrado?"; `start_cmd` maneja el deep-link `/start <code>`; handlers de
  texto/voz/foto responden el mensaje de invitación a no registrados.
- `web.py`: `GET /api/admin/referrals` (links + árbol de referidos), env `BOT_USERNAME` para armar los links.

## [0.7.0] - 2026-06-24
### Added
- **Panel de administrador** (`/app/admin`, solo para admins). Primera versión enfocada en **costos y usuarios**:
  - **Costos:** costo de hoy y del mes, mensajes/llamadas de hoy, y una barra del **tope diario global** (gastado vs US$5) con el recordatorio del límite free (15 msgs/día).
  - **Uso por modelo (mes):** llamadas, tokens in/out y costo por modelo (Haiku / Sonnet).
  - **Usuarios:** lista con plan editable (free / pareja / pro), mensajes de hoy y costo del mes por persona, y activar/desactivar cuenta (con confirmación; no podés desactivarte a vos mismo).
  - **Referidos:** sección preparada (próximamente).
  - Acceso: admin = `telegram_id` en `ADMIN_USER_IDS` (fallback a `ALLOWED_USER_IDS`, la pareja, para que funcione sin config). El link "Admin" aparece en el menú/sidebar solo si sos admin.

### Backend
- `GET /api/me` ahora incluye `is_admin`. Nuevos endpoints (gateados por admin): `GET /api/admin/overview`, `GET /api/admin/users`, `PATCH /api/admin/users/{id}` (plan/activo), `GET /api/admin/usage`. Lectura defensiva de `api_usage`/`users.plan` (no rompe si el bot aún no migró).

### Fixed
- **Landing: animaciones muertas en celulares con "Reducir movimiento".** El código desactivaba **todas** las animaciones si el sistema pedía menos movimiento (iOS/Android lo aplican a Safari, Brave, etc.), dejando la página congelada. Ahora **degrada con elegancia**: mantiene reveals suaves (fades/slides cortos al entrar) y saltea solo lo pesado (smooth-scroll, floats infinitos, parallax de mouse, convergencia de tarjetas, secciones pineadas, crecimiento de la punta, loop del logo, drift de blobs). Los visitantes sin ese ajuste siguen viendo la versión completa.

## [0.6.0] - 2026-06-24
Primera tanda de **controles de costo** en el bot (rumbo a abrir Yumi a más usuarios).

### Backend (bot)
- **Tracking de uso de la API de Claude.** Nueva tabla `api_usage` que registra, por llamada, modelo, tipo (parser / parser_esc / foto / precio / digest), tokens (in/out + cache read/write) y **costo estimado en USD**. Base para el panel de admin y para los topes.
- **Prompt caching** en el parser (bloque `system` con `cache_control: ephemeral`): las consultas seguidas del mismo usuario reusan el prompt cacheado → menos costo por mensaje.
- **Tope global diario** (`DAILY_GLOBAL_CAP_USD`, default **US$5/día**): si el gasto del día llega al tope, el bot pausa con un aviso hasta el día siguiente (red de seguridad anti-abuso/bug). *Fail-open*: si el chequeo falla, deja pasar.
- **Quota por plan** (`FREE_DAILY_MSGS`, default **15 msgs/día** para plan `free`). Nueva columna `users.plan`; la pareja whitelisteada (`ALLOWED_USER_IDS`) queda en plan `pareja` (ilimitado) automáticamente al iniciar. Hoy el bot sigue siendo privado a la pareja; el quota entra en juego cuando se abra a otros.

## [0.5.2] - 2026-06-24
### Fixed
- **Editar precarga los datos.** Los formularios de edición (evento, recordatorio, tarea, cuota, nota, categoría, recurrente, cuenta, movimiento) abrían vacíos; ahora vienen con la info cargada (fix con `key` que remonta el form).
- **Cerrar sesión** ahora va al login de la app (`/app/login`) y vuelve a la app tras loguearte, en vez de caer en el login/dashboard viejo.
- **Hábitos:** se pueden **editar (renombrar) y borrar** desde cada hábito (antes no había forma).

## [0.5.1] - 2026-06-24
### Fixed
- **"A pagar este mes" / "ciclo en curso" ahora incluye las cuotas del mes.** Antes mostraba **$0** en tarjetas cuyo saldo son cuotas (porque las cuotas no son transacciones y el ciclo se calculaba solo desde transacciones). Ahora = compras del ciclo abierto + **una cuota de cada plan activo**, en Inicio, Tarjetas y Hoy. La deuda total (consumos + todas las cuotas) sigue solo en el detalle.
- **Detalle de cuota más claro:** "Cuota N de M · $X c/u" + "Te falta: $Y (N cuotas)". Se sacó el confuso "pagadas 0/M" y el "Total restante" duplicado.

## [0.5.0] - 2026-06-24
### Added
- **Recordatorios vinculados a eventos.** Al crear un evento podés elegir avisos ("avisarme antes": 10 min / 1 h / 2 h / 1 día / 2 días). En la Agenda los recordatorios aparecen **anidados bajo su evento** (con "te aviso 2 días antes"), en vez de como ítems sueltos, y se pueden quitar uno por uno.

### Backend
- `GET /api/eventos` incluye `reminders` (recordatorios linkeados por `event_id`); `POST /api/eventos` acepta `reminder_offsets`; `POST /api/recordatorios` acepta `event_id`.
- Bot: deja de nombrar los recordatorios de eventos como "En N min: …" (texto limpio; ya quedaban linkeados por `event_id`).

## [0.4.0] - 2026-06-24
### Changed
- **"A pagar" reemplaza a "deuda total" en todas las pantallas menos el detalle de la tarjeta.** Inicio, Tarjetas y Hoy muestran como número principal **lo que vence** (ciclo cerrado), no el total. La deuda total (consumos + cuotas por venir) queda solo en el detalle de cada tarjeta (`/tarjetas/:id`).

### Added
- **Home "Hoy" más completo:** nueva sección **"Lo que viene"** con los próximos eventos y recordatorios (después de hoy).

### Fixed
- **Recordatorios:** se limpia el prefijo "En 2880 min: …" que generaba el bot; ahora se ve el texto del recordatorio y la hora a la que avisa.

## [0.3.2] - 2026-06-24
### Added
- Las tarjetas en Inicio/Finanzas ahora son clickeables → abren el detalle de la tarjeta directo, sin pasar por el menú.

## [0.3.1] - 2026-06-24
Coherencia del modelo de plata de las tarjetas: una sola fuente de verdad en `lib/cards.ts`.

### Fixed
- **Contador de cuotas desfasado**: mostraba las cuotas pagadas (1/6) en vez de la cuota actual (2/6). Ahora cuenta igual que el bot: cuota actual = pagadas + 1.
- **“A pagar” inconsistente entre pantallas**: Hoy mostraba el saldo total mientras Tarjetas mostraba la deuda con cuotas. Ahora “A pagar” = ciclo cerrado (lo que vence) en todos lados, y “Deuda total” = consumos + cuotas por venir, por separado.
- **“En cuotas” no coincidía**: el stat de Inicio usaba un cálculo del backend (excluía las pausadas) distinto al de las tarjetas. Unificado: las cuotas pausadas también cuentan como deuda.

### Changed
- El detalle de la tarjeta muestra “A pagar ahora” (resumen cerrado + fecha de vencimiento) además del ciclo en curso.
- Todos los montos de tarjeta se calculan en un solo lugar (`lib/cards.ts`): consumos, cuotas por venir, deuda total, a pagar y cuota actual, con tests unitarios que lo blindan.

## [0.3.0] - 2026-06-24
### Added
- **App instalable (PWA)**: Yumi se puede "Agregar a inicio" en el celular y abre en pantalla completa, con su ícono propio. Incluye Web App Manifest, service worker (Workbox, `registerType: autoUpdate`, scope `/app/` — no toca `/api`), íconos 192/512 (`any maskable`) y `apple-touch-icon` para iOS. Precache del *app shell* (~1.5 MB) → carga aunque haya mala señal. En Android/Chrome aparece "Instalar"; en iPhone, Compartir → Agregar a inicio.

## [0.2.1] - 2026-06-24
### Fixed
- **Notas crasheaba** contra el backend real: `tags` se guarda como string JSON (`json.dumps`) y el front lo trataba como array (`tags.map is not a function`). Ahora `useNotas` normaliza `tags` a `string[]` (parsea el JSON, tolera `null` o coma-separado). Único campo JSON-string que consume la web (verificado contra `vps_current`).

## [0.2.0] - 2026-06-24
Yumi deja de ser solo finanzas: llega **el asistente**. Se suman las 6 secciones del bot a la app y un **Home "Hoy"** que unifica el día.

### Added
- **Home "Hoy"** (nueva pantalla de inicio): tu día (eventos, recordatorios, tareas y recurrentes que tocan hoy), resumen de plata (gastado / a pagar / disponible) y tareas pendientes.
- **Agenda**: eventos + recordatorios unificados, agrupados por día (Hoy / Mañana / fecha), con alta/edición/borrado y *posponer* recordatorios.
- **Tareas**: pendientes ordenadas por prioridad, completar/reabrir, editar y borrar.
- **Listas compartidas**: súper/farmacia/etc., ítems con cantidad, check, limpiar comprados y plantillas.
- **Hábitos**: registro diario, grilla de últimos 7 días y resumen.
- **Notas**: con tags y búsqueda.
- **Búsqueda global**: busca en tareas, notas, eventos, recordatorios y movimientos, agrupado por tipo.
- Botón **+** multi-tipo: cargar gasto, tarea, nota, evento o recordatorio desde un solo lugar.

### Changed
- **Navegación reorganizada** de "finanzas" a "asistente": bottom nav (Hoy · Finanzas · + · Agenda · Tareas), sidebar agrupado (Asistente / Finanzas) y buscador en la barra superior.
- El inicio financiero se movió a `/finanzas`; `/` ahora es el Home "Hoy".

### Fixed
- Agenda agrupaba por día en UTC: eventos de la noche (≥21:00 en Argentina) caían en "Mañana". Ahora usa hora local.
- La búsqueda global crasheaba al tipear (el endpoint de movimientos devuelve `{ items }`, no un array).
- Hábitos mostraba "vezes" → "veces".

## [0.1.0] - 2026-06-24
Base: el **asistente de finanzas de la pareja** (la cuña), web + landing, con marca Yumi.

### Added
- Dashboard React mobile-first (Vite + React 19 + TS + Tailwind v4 + TanStack Query + Radix), estética editorial "NewForm".
- **Finanzas:** Inicio (gastado del mes, a pagar, cuotas, categorías), Movimientos (filtros, selección múltiple, mover/editar/borrar), Tarjetas + detalle de tarjeta (deuda = consumos + cuotas, ciclos, gestión de cuotas con "pagado/falta"), Cuentas (multi-moneda, ajustar saldo), Categorías, Recurrentes y cuotas, Perfil.
- Modelo de plata coherente entre secciones (misma "deuda" en Tarjetas/Detalle/Cuentas/Inicio); centavos; skeletons a medida; modales/desplegables Radix.
- Marca **Yumi**: wordmark, logo y favicon SVG.
- **Landing** animada (GSAP + ScrollTrigger + Lenis, scroll estilo Jeton).
- Deploy: app en `/app`, landing en `/`, dashboard viejo en `/legacy` (Caddy); runbook en `DEPLOY.md`.

### Backend
- `POST/PATCH /api/accounts` acepta `closing_day`/`due_day`; `POST/PATCH /api/recurring` acepta `installments_fired`.

### Pendiente (rumbo a 1.0 — el asistente completo)
- Agenda (eventos + recordatorios), Tareas, Listas compartidas, Hábitos, Notas, Búsqueda global, Home "Hoy" unificado.
