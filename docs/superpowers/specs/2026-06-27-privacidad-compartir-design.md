# Privacidad / Compartir — Diseño

**Fecha:** 2026-06-27
**Estado:** aprobado, listo para plan de implementación
**Feature:** modelo de privacidad de Yumi — todo privado por default; cada usuario comparte con su hogar (pareja/familia) o todo, o por cuenta/ítem. El bot y la web no pueden acceder a la data privada de otro integrante.

## Objetivo

Hoy el modelo es **"hogar compartido"**: dentro de un hogar, un integrante puede ver lo del otro (por consulta del bot tipo "cuánto gastó X", "los dos", o por la web). Queremos invertirlo: **privado por default**, y que cada uno decida compartir **todo** o **ciertas cosas** con su hogar. Crítico (seguridad): ninguna consulta —ni siquiera en lenguaje natural— debe devolver ítems privados de otro.

> El aislamiento **entre hogares distintos** (otra familia no ve nada) ya existe y es sólido (`users.household_id`, auditoría de seguridad). Esto es sobre la privacidad **dentro** de un hogar.

## Decisiones (acordadas)

| Tema | Decisión |
|---|---|
| Finanzas | **Por cuenta**: `accounts.shared` define privado/compartido; los gastos **heredan** de su cuenta (sin flag por gasto) |
| Resto (eventos, recordatorios, tareas, notas, listas) | **Por ítem**: flag `shared` en cada uno |
| Default | **Privado** (`shared=0`) en todo |
| "Compartir todo" | Interruptor maestro por usuario `users.share_all` (default 0) |
| Alcance v1 | **Todas** las entidades a la vez |
| Migración | **Empezar de cero**: todo a `shared=0`, `share_all=0`; cada uno re-comparte |

## Modelo de datos

Columnas nuevas / estandarizadas (migración idempotente en `main.py` init `_ALTERS`):
- `users.share_all` INTEGER DEFAULT 0
- `accounts.shared` INTEGER DEFAULT 0  *(nueva)*
- `eventos.shared` INTEGER DEFAULT 0  *(nueva)*
- `recordatorios.shared` INTEGER DEFAULT 0  *(nueva)*
- `tareas.shared` → estandarizar default a 0 (hoy 1)
- `notas.shared` → default 0
- `lists.shared` → default 0 (hoy 1)

**Migración de datos (empezar de cero) — CRÍTICO que corra UNA sola vez:** setear `shared=0` en accounts/eventos/recordatorios/tareas/notas/lists y `share_all=0` en users. **No puede correr en cada reinicio** (borraría lo que los usuarios vayan compartiendo). Sentinela: una fila en una tabla `app_meta(key,value)` con `key='privacy_reset_done'`; el reset corre solo si esa fila no existe, y al terminar la inserta. (Las columnas nuevas se agregan aparte, idempotente, vía `_ALTERS`.)

**Importante — no confundir con `transactions.is_shared`:** ese flag es de **división de gastos** (shared_expenses / "quién le debe a quién"), un concepto distinto de la **visibilidad**. La visibilidad de un gasto la da **su cuenta** (`account.shared`), no `is_shared`. `is_shared` se mantiene para el feature de saldar, sin rol en visibilidad.

## Regla de visibilidad (el corazón)

Predicado canónico `visible(item, viewer)`:
1. Si `item.owner_user_id == viewer.id` → **True** (lo propio siempre se ve, privado o no).
2. Si el dueño **no** es del hogar de viewer → **False** (aislamiento entre hogares, ya existe).
3. Mismo hogar, otro dueño → **True solo si** `owner.share_all == 1` **OR** `item_shared == 1`, donde:
   - gastos/transacciones: `item_shared = account.shared` (la cuenta del gasto)
   - accounts/eventos/recordatorios/tareas/notas/lists: `item_shared = item.shared`

Semántica de scope (bot y web):
- **`mine`** → `owner_user_id = asker` (todo lo mío).
- **`ours` / `compartido` / `los dos` / `ambos`** → del hogar: `owner = asker` **OR** (`owner ∈ hogar` **AND** (`owner.share_all` OR shared)). Es decir: lo mío + lo compartido por los demás. **Nunca** lo privado ajeno.
- **`user:X`** → `owner = X` **AND** (`X = asker` OR `X.share_all` OR shared). Si X soy yo, todo lo mío; si X es mi pareja, **solo lo compartido de X**.

## Dónde se aplica (enforcement)

**Bot (`main.py`):** `resolve_scope`, `build_consulta_filter`, `_eventos_query`, `_distinct_keyword_candidates`/`_maybe_fuzzy_keyword`, y cualquier consulta que hoy use `household_member_ids` para "ours"/"user:X". El filtro pasa de `user_id IN (miembros)` a `user_id IN (miembros) AND visible(...)`:
- gastos: `JOIN accounts a ON a.id=t.account_id` y condición `t.user_id=asker OR a.shared=1 OR owner.share_all=1`.
- eventos/recordatorios/tareas/notas: `owner=asker OR x.shared=1 OR owner.share_all=1`.

**Web (`web.py` / `crud_v2.py`):** `resolve_scope_uid`, `user_filter`/`user_filter_eq`, listado de cuentas (`api_accounts`), `overview2` (gastos/categorías/cashflow/hoy), notas/tareas/eventos/recordatorios, networth/vencimientos si agregan datos de otros. Misma regla. `crud_v2.assert_ownership(allow_shared=…)` se actualiza para usar el predicado (propio, o compartido-y-visible).

> La regla se centraliza en un helper reutilizable (ej. `visibility_filter(asker_id, entity)` que devuelve el fragmento SQL + params) para no duplicar lógica entre bot y web y poder testearla.

## Cómo se comparte (UX)

**App (React):**
- Ajustes: switch **"Compartir todo con mi pareja"** (`share_all`).
- Cuentas: toggle privado/compartido por cuenta.
- Ítems (evento/tarea/nota/recordatorio/lista): toggle privado/compartido (en su modal/acciones).
- Endpoints: `PATCH` de cada entidad acepta `shared`; `PATCH /api/me` o `/api/settings` acepta `share_all`.

**Bot:**
- Al crear, **privado por default**. Si el texto dice "compartido / con mi pareja / los dos / juntos" → `shared=1` (cuenta o ítem según corresponda). El parser ya extrae un `scope`; se mapea ese scope en creación a la bandera.
- Cuenta compartida al crearla ("cuenta conjunta/compartida") o con comando.
- Comandos: `/compartir [N]` y `/privado [N]` (togglean el último ítem o el #N), `/compartirtodo` y `/privadotodo` (setean `share_all`). Ya existe `/compartir` para tareas → se generaliza.

## Errores / borde
- Un `user:X` que pide lo privado de X → simplemente no aparece (no error, no fuga).
- Items sin dueño (`user_id NULL`, legacy) → tratados como no visibles para otros (ya cubierto por el endurecimiento previo).
- `share_all` es reversible: apagarlo vuelve a ocultar lo no marcado.

## Testing
Tests de **enforcement** (unitarios sobre el helper de visibilidad + de integración sobre las queries):
- Usuario A NO ve un gasto/evento/tarea/nota privada de B (mismo hogar) — por scope `ours` y por `user:B`.
- A SÍ ve un ítem de B marcado `shared=1`.
- A SÍ ve **todo** lo de B si `B.share_all=1`; al apagarlo, deja de verlo.
- A ve **todo lo suyo** (privado + compartido) con `mine`.
- Gastos: visibilidad por `account.shared` (no por `is_shared`).
- Aislamiento entre hogares intacto.
- Bot: `parse`/consulta de "cuánto gastó B" no devuelve privados de B.

## Migración y deploy
- Migración idempotente en `main.py` init (columnas + reset a privado, con sentinela para correr una sola vez).
- Deploy: `main.py` + `web.py` + `crud_v2.py` (backend) + frontend. Reinicio de `asistente` y `asistente-web`.

## Fuera de alcance (v1)
- Compartir selectivo con personas distintas dentro de un hogar >2 (se comparte "con el hogar", no por-persona). Si el hogar tiene 3+, "compartido" = visible para todos los del hogar.
- Permisos de edición (esto es de **lectura/visibilidad**; quién puede editar lo compartido se mantiene como hoy).
