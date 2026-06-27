# Feed de calendario (.ics) — Diseño

**Fecha:** 2026-06-27
**Estado:** aprobado, listo para plan de implementación
**Feature:** suscripción de calendario por URL (.ics) para que el usuario vea sus eventos y recordatorios de Yumi en Google/Apple/Outlook Calendar.

## Objetivo

Que cada usuario pueda **suscribir** su calendario externo (Google/Apple/Outlook) a un feed `.ics` de Yumi y ver ahí sus **eventos** y **recordatorios**. Es la integración de calendario de **menor fricción**: no requiere OAuth ni verificación de Google.

## Alcance

**Incluye (v1):**
- Feed `.ics` **una vía** (Yumi → calendario externo, **solo lectura** en el calendario).
- Contenido: **eventos + recordatorios** del propio usuario (scope propio).
- Ventana temporal: desde **hoy − 30 días** en adelante.
- UI para obtener/copiar la URL y regenerarla.

**Fuera de alcance (v1, futuro):**
- Dos vías / crear eventos desde Google → requiere OAuth de Google (otro spec).
- Vencimientos de tarjeta y tareas en el feed (se decidió NO incluirlos).
- Agenda compartida del hogar (se decidió **solo los míos**).
- Notificaciones/push (ya existen por otro lado).

## Decisiones de diseño (acordadas)

| Tema | Decisión |
|---|---|
| Contenido | Eventos + recordatorios (sin vencimientos ni tareas) |
| Alcance | Solo los del propio usuario (no el hogar) |
| Dirección | Una vía, solo lectura (no OAuth) |
| Ventana | hoy − 30 días en adelante |
| Generación | On-demand (genera el .ics en cada request, sin cache) |
| Auth | Token secreto en la URL (los calendarios no mandan cookies) |
| Librería | `icalendar` (Python) para formato/escapes/timezone correctos |
| Zona horaria | `America/Argentina/Buenos_Aires` con `VTIMEZONE` |

## Arquitectura

### Endpoints (web.py / FastAPI)
- **`GET /api/cal/{token}.ics`** — público (auth por token). Devuelve `text/calendar; charset=utf-8`. Es el que levanta el calendario externo (server-side, cada ~pocas horas; no es tiempo real). Token inválido → 404.
- **`GET /api/cal/url`** — requiere sesión. Devuelve `{ "url": "<base>/api/cal/<token>.ics" }`, creando el token del usuario si no existe.
- **`POST /api/cal/regenerate`** — requiere sesión. Genera token nuevo (invalida el anterior) y devuelve la URL nueva.

La URL absoluta del feed se arma sobre el **dominio raíz** (NO el path `/app`): `https://asistente.emir-maestu.site/api/cal/<token>.ics`. Se toma de un env nuevo `PUBLIC_BASE_URL` (default `https://asistente.emir-maestu.site`), no de `APP_URL` (que incluye `/app`).

### Token y seguridad
- Nueva columna **`users.cal_token`** (TEXT, único, índice). Valor = `secrets.token_urlsafe(24)` (inadivinable).
- Se genera **perezosamente** la primera vez que el usuario pide la URL.
- **Regenerar** = nuevo token → la URL vieja deja de funcionar (revocación).
- El token NO da acceso a login ni a la API; solo al feed de lectura de ese usuario.

### Generación del .ics (módulo nuevo, ej. `calfeed.py`)
Función pura `build_ics(eventos, recordatorios, tz) -> str` (testeable sin DB):
- `VCALENDAR` con `PRODID`, `VERSION:2.0`, `X-WR-CALNAME: Yumi`, y un `VTIMEZONE` de Buenos Aires.
- **Eventos** → `VEVENT`:
  - `DTSTART` = `starts_at` (con `TZID`), `DTEND` = `starts_at` + 1h (default).
  - `SUMMARY` = título; `LOCATION` = ubicación; `DESCRIPTION` = notas.
  - `UID` estable: `yumi-evento-<id>@yumi` (no se duplican al refrescar).
- **Recordatorios** → `VEVENT`:
  - `DTSTART` = `remind_at` (con `TZID`), `DTEND` = +30 min.
  - `SUMMARY` = texto limpio del recordatorio.
  - `VALARM` con `TRIGGER` a la hora del evento (que el calendario avise).
  - Si tiene `recurrence` (daily/weekly/monthly) → `RRULE` (`FREQ=DAILY|WEEKLY|MONTHLY`).
  - `UID` estable: `yumi-rec-<id>@yumi`.
- **Fail-safe:** si un item está mal formado, se saltea (no rompe el feed completo).

### Consulta de datos
- Eventos del usuario: `WHERE user_id=? AND substr(starts_at,1,10) >= (hoy-30d)`.
- Recordatorios del usuario: `WHERE user_id=? AND substr(REPLACE(remind_at,' ','T'),1,10) >= (hoy-30d)` — se incluyen los **ya disparados** dentro de la ventana (sirve ver el historial reciente en el calendario), no solo `fired=0`.
- Scope propio (no hogar).

## UI (web-react)
Tarjeta **"Suscribir a mi calendario"** en la pantalla **Agenda**:
- Explicación corta + la URL del feed con botón **Copiar**.
- Instrucciones rápidas por plataforma (Google: *Otros calendarios → Desde URL*; iPhone: *Ajustes → Calendario → Cuentas → Agregar → Suscrito*).
- Botón **"Regenerar link"** (con confirmación, porque rompe la suscripción anterior).
- Usa `GET /api/cal/url` para mostrar la URL y `POST /api/cal/regenerate` para rotarla.

## Manejo de errores
- Token inválido/inexistente → **404**.
- Usuario sin eventos/recordatorios → `.ics` **válido vacío** (VCALENDAR sin VEVENTs).
- Error generando un item → se saltea ese item.
- Headers correctos (`Content-Type: text/calendar`) para que los clientes lo reconozcan.

## Testing
- **Unit del generador** (`build_ics`): dado un set de eventos/recordatorios → el resultado se **parsea de vuelta con `icalendar`** y se verifica: cantidad de `VEVENT`, `DTSTART/DTEND` con TZID correcto, `VALARM` en recordatorios, `RRULE` en recurrentes, escapes de caracteres especiales (comas, saltos de línea) y `UID` estables.
- Caso vacío → VCALENDAR válido sin eventos.

## Dependencias y migración
- **Dependencia nueva:** `icalendar` (pip en el venv del VPS).
- **Migración:** agregar columna `users.cal_token` (idempotente, en el init de main.py) + índice único.
- **Deploy:** backend (web.py + módulo nuevo + main.py para la columna) + frontend (tarjeta en Agenda). Reinicio de `asistente` y `asistente-web`.

## Riesgos / notas
- Los feeds `.ics` **no son tiempo real**: Google refresca cada varias horas (a veces hasta 24h). Es una limitación del protocolo, se aclara en la UI.
- Las fechas de Yumi se guardan como hora local (naive); al emitir con `TZID` de Buenos Aires quedan correctas para clientes en AR y para viajeros.
