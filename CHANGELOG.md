# Changelog

Todas las novedades relevantes de Yumi. Formato basado en [Keep a Changelog](https://keepachangelog.com/es/), versionado [SemVer](https://semver.org/lang/es/).

> Regla: cada tanda de features = bump de versión (MINOR), entrada en este archivo, tag de git (`vX.Y.Z`) y redeploy. `1.0.0` = lanzamiento del **asistente completo** (no solo finanzas).

## [Unreleased]

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
