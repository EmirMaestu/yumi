# Compartir por integrante (notas / listas / tareas) — spec

**Fecha:** 2026-06-30 · **Estado:** aprobado (modelo + permisos confirmados por el dueño)

Objetivo: compartir cada **nota / lista / tarea** con **integrantes puntuales** del hogar o con **todos**, respetando permisos, sin filtrar contenido privado, y consistente entre todas las cuentas del plan.

## Decisiones confirmadas
- **Granularidad:** privado (default) · con personas puntuales · con todo el hogar.
- **Permisos = "Colaborar":**
  - **Notas:** quien la recibe puede **editar el texto**; **borrar** = solo el dueño.
  - **Tareas:** quien la recibe puede **marcar hecha/pendiente**; editar texto/prioridad y **borrar** = solo el dueño.
  - **Listas:** quien la recibe puede **agregar/tildar/destildar/quitar ítems**; **borrar/renombrar la lista** = solo el dueño.
- **"Tiempo real" = por refetch** (TanStack Query invalida y recarga). No hay websockets; consistente al refrescar/cambiar de pantalla, no push instantáneo.

## Modelo de datos (aditivo)
Nueva tabla (migración idempotente en `main.py` init):
```sql
CREATE TABLE IF NOT EXISTS item_shares (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity TEXT NOT NULL,                 -- 'tareas' | 'notas' | 'lists'
  item_id INTEGER NOT NULL,
  owner_user_id INTEGER,
  shared_with_user_id INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(entity, item_id, shared_with_user_id)
);
CREATE INDEX IF NOT EXISTS idx_item_shares ON item_shares(entity, item_id, shared_with_user_id);
```
Se mantiene la columna booleana `shared` = "con todo el hogar" (atajo). Un ítem es visible si: **propio** · `share_all` del dueño · `shared=1` · **o** hay fila en `item_shares` para mí. Todo **acotado al hogar**.

## Regla de visibilidad (lectura)
Extender `shared_expr` para tareas/notas/lists con un EXISTS (sin params, valores embebidos seguros: entity literal, asker_id int):
```
shared_expr_item_member(alias, entity, asker) =
  ({alias}.shared=1
   OR EXISTS (SELECT 1 FROM item_shares s
              WHERE s.entity='{entity}' AND s.item_id={alias}.id
                AND s.shared_with_user_id={asker}))
```
`visibility.where` ya envuelve con el `share_all` del dueño y acota a `members` del hogar.

## Permisos de escritura
Helper nuevo `can_collaborate(conn, entity, item_id, user)` = **dueño** O (mismo hogar Y (`shared=1` O dueño con `share_all` O fila en `item_shares` para el user)).
- Acciones "colaborar" usan `can_collaborate`: nota editar texto; tarea done/undone; lista add/toggle/del-item/clear/buy-all.
- Acciones "solo dueño" usan `owner == user`: borrar nota/tarea/lista, editar texto/prioridad de tarea, renombrar lista.
- Reemplaza/extiende `_can_touch_shared` (web.py) y `assert_ownership(allow_shared=True)` (crud_v2) para incluir el caso per-member.

## API
- **`POST /api/share`** (extender): body `{entity, id, shared?:0|1, members?: number[]}`. Solo dueño. Setea `shared`; si viene `members`, **reemplaza** las filas de `item_shares(entity,id)` por esos ids (validados: deben ser del hogar del dueño). entity ∈ {tareas, notas, lists}.
- **`GET /api/share?entity=&id=`** (nuevo): devuelve `{shared, members: number[]}` para prefilar la UI. Solo dueño.
- **`GET /api/household/members`** (nuevo): `[{id, name}]` del hogar (para el selector). (Hoy `me.others` da nombre+scope_value pero no id.)

## Call-sites a tocar (CRÍTICO — todos o ninguno para no filtrar)
**Lectura (agregar el EXISTS per-member donde entity ∈ tareas/notas/lists):**
- `web.py` `vis_filter_item` → aceptar `entity` opcional; GET tareas, GET notas.
- `crud_v2.py` `get_listas` (y plantillas si aplica).
- `main.py` (bot) lecturas de tareas/notas/listas (consultas + "compartido"). *(Acá fue el incidente previo — revisar con lupa.)*

**Escritura (aplicar la matriz):**
- `web.py`: tareas done/undone (colaborar) vs editar/borrar (dueño); notas editar (colaborar) vs borrar (dueño).
- `crud_v2.py`: ops de ítems de lista (colaborar) vs borrar/renombrar lista (dueño); `assert_ownership`.
- `main.py` (bot): mismos chequeos en los callbacks/intents de listas/tareas/notas.

## Frontend
- Acción **"Compartir"** en cada tarea/nota/lista → hoja con: **Todos** (toggle `shared`) o **personas** (checkboxes de `/api/household/members`), prefilada con `GET /api/share`.
- Indicador visual de "compartida con N" / "privada".
- Invalidaciones: tras compartir o editar, invalidar las listas afectadas (consistencia entre cuentas al refetch).

## Plan por fases (cada fase intermedia NO filtra)
1. **Base (segura):** migración `item_shares` + `visibility.shared_expr_item_member` + `can_collaborate` helper + **tests pytest** de la SQL de visibilidad y permisos. Sin cambiar call-sites → sin cambio de comportamiento.
2. **Activación lectura:** wire del EXISTS en web/crud/bot (tareas/notas/lists).
3. **Activación escritura:** matriz de permisos en web/crud/bot.
4. **API share** (members + GET) + `/api/household/members`.
5. **Frontend:** UI de compartir + indicadores + invalidaciones.
6. **Revisión de seguridad + tests cruzados:** A comparte con B (no C) → B ve/colabora, C no ve; borrar = solo dueño; al quitar del hogar, se cae el acceso; sin inconsistencias entre cuentas.

## Criterios de aceptación
- Nunca se filtra contenido privado.
- Compartido solo visible para autorizados (per-member o todos).
- Permisos "Colaborar" exactos por entidad.
- Consistencia entre cuentas (mismas vistas/acciones tras refetch).
- Tests de visibilidad/permisos en verde antes de dar por terminado.
