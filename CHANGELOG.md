# Changelog

Todas las novedades relevantes de Yumi. Formato basado en [Keep a Changelog](https://keepachangelog.com/es/), versionado [SemVer](https://semver.org/lang/es/).

> Regla: cada tanda de features = bump de versión (MINOR), entrada en este archivo, tag de git (`vX.Y.Z`) y redeploy. `1.0.0` = lanzamiento del **asistente completo** (no solo finanzas).

## [Unreleased]

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
