# Changelog

Todas las novedades relevantes de Yumi. Formato basado en [Keep a Changelog](https://keepachangelog.com/es/), versionado [SemVer](https://semver.org/lang/es/).

> Regla: cada tanda de features = bump de versión (MINOR), entrada en este archivo, tag de git (`vX.Y.Z`) y redeploy. `1.0.0` = lanzamiento del **asistente completo** (no solo finanzas).

## [Unreleased]

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
