# Asistente Personal — Handoff bundle

Bundle del proyecto para que otro agente (humano o IA) pueda continuar el trabajo.

## Que es esto

Bot de Telegram + dashboard web para gestion personal y financiera multi-usuario.
Pensado para parejas/familias chicas que comparten algunos gastos pero mantienen
cuentas propias. Optimizado para espanol rioplatense y tarjetas argentinas
(Naranja, Visa, Santander, Mercado Pago).

Lee `docs/informe_proyecto_asistente.pdf` para el detalle completo de capacidades.

## Stack

- **Bot Telegram**: Python + `python-telegram-bot`
- **NLP / Vision**: Claude Sonnet/Haiku (Anthropic API)
- **Transcripcion audio**: Whisper local (faster-whisper)
- **Web**: FastAPI + Uvicorn
- **Dashboard frontend**: HTML/JS vanilla embebido
- **DB**: SQLite (un solo archivo: `data.db`)
- **Reverse proxy**: Caddy con HTTPS automatico
- **Hosting**: VPS Linux (Ubuntu 22.04+) en `217.76.48.219`
- **Servicios systemd**: `asistente` (bot) y `asistente-web` (dashboard)

## Estructura de carpetas

```
asistant/
├── README.md                  Este archivo
├── docs/
│   └── informe_proyecto_asistente.pdf   Informe completo del producto (12 paginas)
├── src_original/              Codigo TAL CUAL estaba al inicio del proyecto
│   ├── main.py                Bot principal (original, antes de patches)
│   ├── web.py                 Dashboard web (original)
│   └── crud_v2.py             CRUD endpoints (original)
├── vps_current/               Codigo ACTUAL del VPS (poblar con bundle_from_vps.sh)
│   ├── main.py
│   ├── web.py
│   ├── crud_v2.py
│   ├── vencimientos.py
│   ├── dashboard.html
│   ├── .env.example
│   └── ...
├── patches/                   Scripts de parche aplicados durante el desarrollo
│   ├── apply_compartir_fixes.py
│   ├── apply_mobile_fixes.py
│   ├── apply_photo_cuotas.py (v1)
│   ├── apply_photo_cuotas_v2.py
│   ├── apply_photo_cuotas_v3.py
│   ├── apply_photo_cuotas_v4.py
│   ├── apply_photo_cuotas_v5.py
│   ├── apply_shared_patches.py
│   ├── apply_shared_web_patches.py
│   ├── apply_vencimientos_patches.py
│   ├── apply_vencimientos_widget.py
│   ├── extract_html.py
│   └── vencimientos.py        (modulo importable)
├── migrations/                Scripts de migracion de DB
│   ├── migrate_multiuser.py
│   ├── migrate_shared.py
│   ├── migrate_tarjetas.py
│   └── fix_accounts_unique.py
└── screenshots/               Capturas del proyecto en uso
    └── (poner manualmente desde el celu o el dashboard)
```

## Como llegamos hasta aca (historial resumido)

1. **Punto de partida** (`src_original/`): bot single-user funcional con NLP basico, fotos, recurrentes, agenda, tareas, habitos, notas. Dashboard web sin login.

2. **Mejora de consultas inteligentes** (no hay patch separado — se integro en main.py):
   - Schema enriquecido para consultas (filtros, agregaciones, periodos).
   - Comandos tipo "cuanto gaste en combustible este mes?" y "mostrame mis ultimas 2 transacciones".

3. **Multi-usuario** (`migrations/migrate_multiuser.py`):
   - Tabla `users`. Columna `user_id` en todas las tablas de datos.
   - Login por contrasena para el dashboard. Filtros por usuario.
   - Comando `/password` para cambiar la contrasena desde el bot.

4. **UNIQUE constraint fix** (`migrations/fix_accounts_unique.py`):
   - Quitar UNIQUE de `accounts.name` para que cada usuario pueda tener una "Tarjeta Santander" propia.

5. **Cuentas compartidas** (`migrations/migrate_shared.py` + `patches/apply_shared_patches.py` + `patches/apply_shared_web_patches.py`):
   - Columna `shared` en `tareas` y `notas`.
   - Comando `/compartir todas` (comparte todas las tareas) y `/compartir off`.
   - Comando `/compartidos` (lista lo compartido entre los dos).
   - Dashboard endpoints filtran incluyendo items con `shared=1`.

6. **Tarjetas con cierre y vencimiento** (`migrations/migrate_tarjetas.py` + `patches/apply_vencimientos_patches.py` + `patches/vencimientos.py`):
   - Columnas `closing_day` y `due_day` en `accounts`.
   - Comando `/vencimientos` y endpoint `/api/vencimientos`.
   - Logica para que cuotas caigan en la fecha de cierre, no del dia de compra.

7. **Widget de vencimientos en dashboard** (`patches/apply_vencimientos_widget.py`):
   - Card visual con los proximos pagos por tarjeta arriba del dashboard.

8. **Foto de cuotas con confirmacion** (`patches/apply_photo_cuotas*.py` v1 a v5):
   - El bot detecta multiples compras en cuotas en una sola imagen (incluye "Cuotas de consumos anteriores").
   - Pregunta con botones si el monto es TOTAL o por CUOTA.
   - **v5 (final)**: ninguna cuota se carga el dia del registro; todas caen en la fecha de cierre de la tarjeta. Cuotas pasadas no se duplican.

9. **Compartir mejorado** (`patches/apply_compartir_fixes.py`):
   - Bug fix de `/compartir todas` que mostraba la ayuda.
   - Feedback con preview de items compartidos.
   - Comando `/compartidos`.

10. **Mobile UI** (`patches/apply_mobile_fixes.py`): CSS overrides para que tablas y nav scrolleen lateralmente en mobile. **Esta parte quedo a medias** (tablas se ven raras en algunas vistas — ver pendientes).

## Pendientes y bugs conocidos

- **Mobile UI**: la nav inferior se corta, las tablas (especialmente recurrentes) se ven con texto desplazado. Hay que rehacer el CSS o convertir tablas a layout tipo "card por fila" en mobile.
- **Listas con nombre**: el usuario tiene mecanismos para agrupar tareas en "listas" (Super, Farmacia, etc.) pero no esta formalizado. La consulta "muestrame mis listas" devuelve solo una; deberia devolver todas. **Falta confirmar** si esta usando notas con texto formateado o tareas con algun tag.
- **Cuotas v5**: aplicado correctamente, pero hay datos viejos (Merpago cuota 1/6 cargada como tx del 22/JUN) que el usuario tendria que limpiar manualmente.
- **Categorias desde el chat**: actualmente solo se crean desde el dashboard o por SQL. Seria nice-to-have un intent `crear_categoria` similar a `crear_cuenta`.
- **Modo Splitwise**: no implementado. Solo se ven gastos juntos, no se balancean automaticamente.
- **Recurrentes solo mensuales**: no hay frecuencia semanal/anual.
- **Comparaciones temporales**: no entiende "cuanto mas gaste este mes que el pasado?" en una sola pregunta.

## Acceso al VPS

- SSH: `ssh emir@217.76.48.219`
- Path del proyecto: `~/asistente/`
- Servicios: `sudo systemctl {start|stop|restart|status} asistente` (bot) / `asistente-web` (dashboard)
- Logs: `sudo journalctl -u asistente -n 50`
- DB: `~/asistente/data.db` (SQLite)
- Config: `~/asistente/.env`
- Venv: `~/asistente/venv/bin/python`
- URL publica: https://asistente.emir-maestu.site

## Para poblar `vps_current/` con el codigo en vivo

En el VPS:

```bash
cd ~/asistente
tar czf /tmp/asistente_bundle.tar.gz \
    main.py web.py crud_v2.py vencimientos.py dashboard.html \
    *.py.bak.* 2>/dev/null
```

Despues desde tu PC:

```powershell
scp emir@217.76.48.219:/tmp/asistente_bundle.tar.gz $env:USERPROFILE\Downloads\
```

Y descomprimi adentro de `asistant/vps_current/`.

(O usa el script `bundle_from_vps.sh` que esta en este folder.)

## Para que un agente continue el trabajo

Recomendaciones de orden:

1. **Leer** `docs/informe_proyecto_asistente.pdf` para entender el alcance.
2. **Mirar** los archivos en `vps_current/` (estado real) y comparar con `src_original/` (punto de partida) para entender la evolucion.
3. **Probar** la web en https://asistente.emir-maestu.site (credenciales en `.env`).
4. **Atacar** los pendientes en este orden sugerido:
   1. Mobile UI (alto impacto visual, prioridad de uso real)
   2. "Listas con nombre" (depende de descubrir como las usa Lisa)
   3. Crear categorias desde el chat
   4. Modo Splitwise (feature commercializable)

## Ambiente local para dev

```bash
git init  # si arrancas con repo limpio
python3 -m venv venv
source venv/bin/activate
pip install python-telegram-bot anthropic fastapi uvicorn faster-whisper python-dotenv pydantic
# para correr localmente vas a necesitar tu propio TELEGRAM_TOKEN y ANTHROPIC_API_KEY
```

## Contacto / dueno del proyecto

- Emir (`@assistant_emir_bot` en Telegram, Telegram ID `6583865360`)
- Usuario adicional: Lisa (Telegram ID `6655744140`)
