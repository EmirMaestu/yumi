# Yumi — spec del bot + harness de review por LLM

Objetivo: que **cualquier LLM** pueda auditar el "cerebro" de Yumi (el parser de intenciones) e **imaginar escenarios de chat que hoy NO están cubiertos** (como el usuario que quiso una lista de campamento y terminó en la lista de súper), reportando gaps priorizados y parches concretos.

Uso: copiá la **Parte D (prompt listo)** en ChatGPT/Claude/etc. Incluye adentro la spec (Parte A) + la misión (Parte B) + el loop (Parte C). La Parte E es una primera pasada ya hecha (para arrancar con gaps reales).

> Fuente de verdad de la Parte A: `vps_current/main.py` → `PARSER_TEMPLATE` (línea ~1490) y la lógica de listas (`_resolve_list`/`_guess_list_meta`/`_LIST_HINTS`, ~1053-1120). Pegado acá al **2026-07-10**; si el prompt cambia, re-sincronizar.

---

## Parte A — Qué tiene el bot (ground truth)

### Superficies
- **Mismo cerebro en Telegram y WhatsApp** (WhatsApp entra por webhook y reusa `process_text`). También hay app web, pero el chat lo maneja este parser.
- Flujo: mensaje del usuario → `parse_intent` (Claude con el prompt de abajo) → devuelve **SIEMPRE un array** de `acciones` vía la tool `registrar_acciones` → cada acción se ejecuta contra la DB → se responde por chat.
- Multi-inquilino: aislamiento por **hogar** (`household_id`). Privacidad por `scope` (mine/ours/user:X). Un usuario **nunca** puede registrar a nombre de otro.
- Control de costo: tope diario global de US$ + cuota diaria del plan free (si se pasa, frena antes de parsear).

### El prompt del parser (verbatim; los `__PLACEHOLDER__` se rellenan en runtime con fecha/hora/cuentas/categorías/otros-usuarios)

```
Sos el parser de un asistente personal en espanol rioplatense (finanzas, agenda, tareas, habitos, notas).
Tu UNICA salida es la tool `registrar_acciones` con un array `acciones`.

HOY: __TODAY__ (__DOW__) - HORA: __NOW__ - TZ: __TZ__
QUIEN ESCRIBE: __ME__ (id=__ME_ID__).
OTROS USUARIOS: __OTHERS__

CUENTAS DE __ME__ (usa el nombre EXACTO en `account`): __ACCOUNTS__
CATEGORIAS (compartidas): __CATEGORIES__

REGLA DE ORO: SIEMPRE UN ARRAY. Un mensaje puede traer VARIAS acciones de tipos distintos.
Separadores: "y", "tambien", saltos de linea, vinetas. JAMAS sumes montos de items distintos.

TABLA DE DECISION:
1. Verbo en pasado sobre dinero (pague, gaste, compre, cobre, me pagaron) -> transaccion
2. Verbo en pasado sobre actividad personal (hice, entrene, lei, corri, medite) -> habito
3. Movimiento entre dos cuentas propias (pase/converti/mande de X a Y) -> transferencia
4. Pago repetido o en cuotas (todos los meses, N cuotas, agenda <servicio>) -> recurrente
5. recordame/avisame/acordame + momento futuro -> recordatorio. Con fecha u hora explicita es SIEMPRE recordatorio.
6. Cita con persona/lugar/hora (cena con, turno, reunion) -> evento
7. Pendiente accionable SIN momento exacto (tengo que, hay que) -> tarea
8. anota/apunta/acordate que/idea: -> nota
9. "crear cuenta X" / "nueva cuenta Y" -> crear_cuenta ; 9b. renombrar cuenta -> editar_cuenta
10. Pregunta sobre datos (cuanto gaste, que tengo) -> consulta
11. borra/move/edita/cambia con #IDs o filtros -> eliminar/mover/editar
12. Nada matchea -> desconocido con data.aclaracion = UNA pregunta concreta

MULTI-USUARIO: default consultas de __ME__. Si mencionan a otro -> filters.scope (mine|ours|user:<nombre>).
Para REGISTRAR nunca a nombre del otro -> desconocido con aclaracion.

MONTOS (AR): luca=1000, media luca=500, palo=1000000, gamba=100, 2k=2000, 1.500=1500 (punto=miles), dolares/u$s->USD, default ARS.
FECHAS: resolver TODO a ISO usando HOY. manana=+1d, el viernes=mas proximo, fin de mes=ultimo dia, recordatorio sin hora->09:00.

INTENTS y CAMPOS de `data`:
- transaccion {type,amount,currency,category,account,description,occurred_at}
- transferencia {amount,from_account,to_account,from_currency,to_currency,exchange_rate,rate_type,description,occurred_at}
- recurrente {type,amount,currency,category,account,description,frequency,day_of_month,next_occurrence,total_installments}
- mover/eliminar/editar {filters|id...}
- evento {title,starts_at,location,notes,kind:"turno"|null,reminder_offsets:[int]|null}
- recordatorio {text,remind_at,recurrence:"daily"|"weekly"|"monthly"|null}
- tarea {text,priority,due_at}
- habito {name,value,unit,note}
- nota {text,tags}
- crear_cuenta {name,type} / editar_cuenta {old_name,new_name}
- consulta {type,intencion,filters{keyword,category,account,type,currency,period,date_from,date_to,amount_min,amount_max,scope},limit,group_by,order,compare_period}
- gasto_compartido {amount,currency,category,account,description,other_share}
- saldar {}
- meta_ahorro {name,target_amount,currency,deadline,add_amount}
- lista_compra {action:"add|check|uncheck|remove|show|clear|bought|remind|save_template|use_template", list:str|null, item:str|null, amount, account, currency, remind_at, target_date, recurrence}
    list=nombre de la lista, null=la de compras por defecto ("Súper"). "agregá los ingredientes de <plato>" -> un add por ingrediente.
- alerta_dolar {rate_type,direction,threshold} / set_takenos_rate {value} / dolar {}
- precio {query} / afford {afford_amount,currency,afford_category} / desconocido {aclaracion}

confidence: 0.9+ inequivoco, 0.6-0.85 algun campo inferido, <0.5 mejor desconocido.
(Sigue una batería de EJEMPLOS por intent — ver main.py.)
```

### Lógica post-parseo que sorprende (importante para el review)
- **Listas:** `list=null` → cae a la lista **"Súper"** por defecto (`_default_list_id`/`_resolve_list`). Si `list="<nombre>"` y no existe, **la crea**. El icono/tipo lo adivina `_guess_list_meta` por palabras clave (`_LIST_HINTS`): súper/compras/mercado→🛒, farmacia/remedio→💊, ferretería/obra→🔧, verdulería/fruta→🥬, regalo/cumple→🎁, vacaciones/viaje/valija→🧳, librería/útiles/escuela→✏️, cumpleaños/fiesta/asado→🎉; **cualquier otra cosa → 📝 genérica**. No hay hint para "campamento", "mudanza", "obra en casa", etc.
- **Listas nacen PRIVADAS** (cambio reciente): una lista creada por chat solo la ve quien la creó hasta que la comparta. En pareja, "agregá leche a la lista" ya **no** la ve el otro automáticamente (salvo `share_all`).
- **Recordatorios sin hora → 09:00**. Recordatorios recurrentes se re-agendan.
- **desconocido** → el bot hace **una** pregunta de aclaración (no inventa).

### Catálogo de intents (resumen)
finanzas: transaccion, transferencia, recurrente, gasto_compartido, saldar, meta_ahorro, afford, dolar/alerta_dolar/set_takenos_rate, precio, mover/eliminar/editar, crear_cuenta/editar_cuenta · agenda: evento, recordatorio · productividad: tarea, habito, nota, lista_compra · lectura: consulta · fallback: desconocido.

---

## Parte B — Misión del revisor (goal)

Sos un **auditor adversarial** del parser de Yumi. Tu objetivo: **encontrar mensajes de chat realistas (español rioplatense) que un usuario real mandaría y que el bot maneja MAL o no cubre.**

Para cada mensaje que generes:
1. **Predecí** el `array` de acciones que devolvería el parser (según la spec de la Parte A) y **qué haría el bot** al ejecutarlo.
2. Emití un **veredicto**: `COVERED` (bien) · `GAP` (no cubierto / se pierde info / cae en default equivocado) · `RISKY` (ambiguo / peligroso / depende del azar del LLM).
3. Si es GAP/RISKY: **severidad** (alta/media/baja), **por qué falla**, y un **parche concreto** (una regla o un ejemplo nuevo para el prompt, o un ajuste de lógica).

Enfocá en gaps que le **pasarían a un usuario común**, no en casos rebuscados. Priorizá: pérdida silenciosa de datos, default equivocado, clasificación cruzada (una cosa termina como otra), privacidad, montos/fechas mal resueltos, multi-intent mal separado.

---

## Parte C — El loop

Repetí **rondas** hasta cubrir todas las categorías o hasta 2 rondas seguidas sin gaps nuevos:

**Rotación de categorías** (una por ronda, en orden; volvé a empezar si hace falta):
1. Listas **no-supermercado** (campamento, mudanza, viaje, obra, cumple, bebé, botiquín, colegio).
2. "Lista de cosas para **hacer**" vs "lista de **compras**" (tarea vs lista_compra).
3. Montos raros: en palabras ("mil quinientos"), decimales ("2,5 palos"), sin cuenta, moneda mixta.
4. Fechas/tiempos: relativos raros ("en 3 días hábiles", "el finde", "a fin de mes"), inválidos (29/2 no bisiesto), ambiguos ("el jueves" ya pasó esta semana).
5. Multi-intent en un mensaje (gasto + recordatorio + nota juntos) y separación correcta.
6. Multi-usuario / privacidad (registrar por el otro, consultas "los dos", scope).
7. Hábito vs tarea vs recordatorio (querer/tener que/hice/recordame + actividad).
8. Consultas complejas (períodos custom, agrupar, comparar, rankings, filtros combinados).
9. Cuentas: alias no listados, crear con nombre raro, transferencia con FX.
10. Destructivos/ambiguos ("borrá todo", "cambiá eso", sin #ID) — ¿confirma o rompe?
11. Cultural/typos/voz: abreviaturas, sin tildes, mensajes de voz transcritos, jerga.
12. Listas compartidas: como ahora nacen privadas, ¿el usuario espera que la pareja la vea?

**Por ronda:** generá **8-12 mensajes** variados de esa categoría, corré los 3 pasos de la Parte B para cada uno, y **deduplicá** contra los gaps ya encontrados (no repitas el mismo gap con otro ejemplo).

**Salida final:** una **tabla priorizada de gaps** (severidad, categoría, ejemplo que lo dispara, comportamiento actual vs esperado, parche propuesto) + un bloque de **parches sugeridos para el prompt** (reglas/ejemplos nuevos, listos para pegar en `PARSER_TEMPLATE`).

---

## Parte D — Prompt listo para pegar en un LLM

> Pegá TODO esto (incluí vos el contenido de la Parte A completa arriba, o linkéalo). El LLM ya queda con spec + misión + loop.

```
Sos un auditor adversarial del parser de intenciones de "Yumi", un asistente personal por chat
en español rioplatense. Te paso ABAJO la especificación exacta del bot (su prompt de parseo y su
lógica de listas). Tu trabajo: encontrar mensajes realistas que un usuario real mandaría y que el
bot maneja MAL o no cubre.

Método (repetí en rondas, una categoría por ronda, hasta 2 rondas seguidas sin gaps nuevos):
- Categorías: 1) listas no-supermercado  2) "lista de cosas para hacer" vs compras  3) montos raros
  4) fechas/tiempos raros o inválidos  5) multi-intent  6) multi-usuario/privacidad  7) hábito vs
  tarea vs recordatorio  8) consultas complejas  9) cuentas/FX  10) destructivos ambiguos
  11) typos/jerga/voz  12) listas compartidas (nacen privadas).
- Por ronda generá 8-12 mensajes variados de esa categoría. Para cada uno:
   (a) predecí el array de "acciones" que devolvería el parser y qué haría el bot;
   (b) veredicto COVERED / GAP / RISKY;
   (c) si GAP/RISKY: severidad (alta/media/baja), por qué falla, y un parche concreto
       (regla o ejemplo nuevo para el prompt, o ajuste de lógica).
- Deduplicá gaps. Al final: tabla priorizada de gaps + parches listos para pegar en el prompt.
Enfocate en lo que le pasaría a un usuario común: pérdida silenciosa de datos, default equivocado,
clasificación cruzada, privacidad, montos/fechas mal resueltos, multi-intent mal separado.

=== ESPECIFICACIÓN DEL BOT (Parte A) ===
<pegá acá la Parte A completa de este documento>
```

---

## Parte E — Primera pasada (ya hecha, para arrancar)

Muestra del método con gaps **reales** encontrados (predicción del comportamiento según la spec):

| # | Mensaje del usuario | Predicción del bot | Veredicto | Sev | Parche |
|---|---|---|---|---|---|
| 1 | "hacé una lista para el campamento: carpa, bolsa de dormir, linterna, repelente" | `lista_compra add` × 4 **sin `list`** → caen en **Súper** (no hay ejemplo de lista no-súper) | **GAP** | alta | Regla+ejemplo: si el mensaje nombra un propósito no-supermercado (campamento, viaje, mudanza, cumple, obra, botiquín), poné `list:"<ese nombre>"`. Ej: "…para el campamento: carpa, bolsa" → adds con `list:"Campamento"`. |
| 2 | "hacé una lista de cosas para hacer antes de viajar: sacar plata, cargar nafta, imprimir pasajes" | Riesgo: como dice "lista", va a `lista_compra` (compras) en vez de **tareas** | **GAP** | alta | Regla: "lista de cosas para **hacer**/pendientes/checklist de acciones" → `tarea` (una por ítem); "lista de **compras/cosas que comprar**" → `lista_compra`. Ejemplo de cada uno. |
| 3 | "agregá leche a la lista" (en pareja) | Crea/usa lista **privada** → la pareja **no la ve** (cambio reciente "todo nace privado") | **RISKY** | alta | Decisión de producto: ¿las listas del súper deberían nacer compartidas en un hogar de 2? Si sí, default `shared=1` para listas creadas por chat cuando el hogar tiene >1 miembro; o avisar "creé la lista (privada, compartila con 👥)". |
| 4 | "gasté mil quinientos en el súper" | Monto en **palabras**: puede no resolver 1500 (los ejemplos son numéricos/lucas) | **RISKY** | media | Ejemplo con monto escrito en palabras ("mil quinientos"=1500, "dos lucas y media"=2500). |
| 5 | "Lisa gastó 5000 en nafta" | `desconocido` con aclaración "solo puedo registrar tus propios gastos" | **COVERED** | — | (privacidad OK) |
| 6 | "recordame el 29 de febrero llamar al gestor" | Año no bisiesto → fecha inválida; puede generar `remind_at` roto o saltar de año | **RISKY** | media | Regla: si la fecha no existe en el año, pedí aclaración o usá el próximo año bisiesto. |
| 7 | "borrá todo" | `eliminar` con filtros vagos → potencial borrado masivo | **RISKY** | alta | Regla: acciones destructivas sin #ID o con filtro amplio → `desconocido`/confirmación explícita antes de borrar. Verificar que el ejecutor pida confirmación. |
| 8 | "anotá la idea del kiosco y recordame llamar al contador mañana 10am" | array = `nota` + `recordatorio` (multi-intent) | **COVERED** | — | (multi-intent OK) |
| 9 | "quiero ir al gimnasio 3 veces por semana" | No hay intent de **meta/hábito recurrente** (hábito es solo log en pasado) → probable `tarea` o `desconocido` | **GAP** | media | Definir si se soporta "meta de hábito"/streak objetivo; si no, responder claro. |
| 10 | "cuánto gasté en comida los últimos 3 meses, mes a mes" | `period` no tiene "últimos 3 meses"; `group_by` no agrupa por mes → responde parcial | **GAP** | media | Agregar período "ultimos_N_meses" y `group_by:"month"`, o aclarar el límite. |

**Gaps semilla priorizados:** (alta) listas no-súper caen en Súper · listas "para hacer" van a compras · listas nacen privadas en pareja · destructivos sin confirmación. (media) montos en palabras · fechas inválidas · metas de hábito · períodos custom en consultas.

**Parche de arranque para el prompt (listas):** agregar a la sección `lista_compra` y a los EJEMPLOS:
```
Si el usuario pide una lista para un PROPÓSITO que no es el supermercado (campamento, viaje,
mudanza, cumpleaños, obra, botiquín, colegio, bebé), poné list="<ese propósito>" en cada add
(no la lista de compras por defecto). Si dice "lista de cosas para HACER / pendientes / checklist
de tareas", devolvé `tarea` por ítem, NO lista_compra.
Ej: "hacé una lista para el campamento: carpa, bolsa de dormir, linterna"
-> [{"intent":"lista_compra","data":{"action":"add","list":"Campamento","item":"carpa"}}, ...]
Ej: "lista de cosas para hacer antes del viaje: sacar plata, cargar nafta"
-> [{"intent":"tarea","data":{"text":"Sacar plata"}},{"intent":"tarea","data":{"text":"Cargar nafta"}}]
```

---

## Cómo correrlo
- **A mano:** pegá la Parte D + la Parte A en cualquier LLM y dejalo iterar.
- **Con `/loop`:** en una sesión de Claude Code, `/loop` con la Parte D como prompt; cada firing hace una ronda y acumula gaps.
- **Actualizá la Parte A** si cambia `PARSER_TEMPLATE` (si no, el review audita una versión vieja).
