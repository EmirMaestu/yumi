# CI/CD + infra del proyecto Yumi — Design

**Fecha:** 2026-06-28
**Estado:** Aprobado (diseño) — pendiente plan de implementación
**Autor:** Emir + Claude

## Problema

Hoy el "source of truth" está partido y el deploy es artesanal:

- El repo GitHub (`EmirMaestu/yumi`, rama `main`) tiene el código bueno, pero el VPS corre
  archivos que se copian a mano por `scp` + swaps con `sudo`.
- El `~/asistente` del VPS *es* un repo git, pero quedó viejo (rama `master`, commit
  `41d2b43`, sin remote sincronizado) y está lleno de `apply_*.py` y `.bak` de parches sueltos.
- Cada deploy implica escribir comandos largos en consola (`scp` + `ssh -t … sudo …`).
- No hay protección de ramas, ni versionado automático, ni forma de ver "qué se subió" salvo
  leer commits sueltos.

**Objetivo:** profesionalizar el flujo — deploy automatizado, ramas protegidas, versionado por
releases, y visibilidad vía PRs/Releases en GitHub. Todo sin reescribir cómo corre el proyecto
(seguimos con systemd + Caddy), dejando la puerta abierta a Docker el día que haga falta.

## Estado actual del VPS (relevado)

- `/home/emir/asistente/` — run-dir del Python. Contiene `main.py` (bot), `web.py` (web),
  `crud_v2.py`, `calfeed.py`, etc., `venv/`, `.env`, `data.db`, `backups/`, `backup_db.py`,
  `vapid_private.pem`, `credenciales*`. Es un repo git desordenado.
- systemd:
  - `asistente` → `User=emir`, `WorkingDirectory=/home/emir/asistente`,
    `EnvironmentFile=…/.env`, `ExecStart=…/venv/bin/python …/main.py`.
  - `asistente-web` → idem, `ExecStart=…/venv/bin/uvicorn web:app --host 127.0.0.1 --port 8000`.
- Caddy sirve: `/var/www/juntu` (frontend React, `root:root`), `/var/www/yumi-landing`
  (landing, `root:root`), y `reverse_proxy 127.0.0.1:8000` para la API.
- `sudo` **requiere contraseña** (no passwordless).
- Mapeo repo→VPS: `vps_current/*.py` → `/home/emir/asistente/*.py`; `web-react/` build →
  `/var/www/juntu`; `landing/` → `/var/www/yumi-landing`.

## Flujo objetivo (día a día)

1. Rama `feat/...` → PR.
2. GitHub corre **checks** (build frontend + tests backend). Si fallan, no se puede mergear.
3. Merge a `main` → **STAGING se actualiza solo**. Se prueba ahí.
4. Cuando está fino → botón **"Release"** en GitHub (se elige `vX.Y.Z`) → **deploy a
   PRODUCCIÓN** con backup + health-check + rollback. Si algo falla, **avisa solo al owner**.

Cero comandos en consola. Todo trazable en GitHub (PRs, Releases, logs de Actions).

## Decisiones tomadas

- **Disparador de deploy a prod:** crear una **release/tag** (`vX.Y.Z`). Los merges a `main` NO
  publican a prod (publican a staging).
- **Protección de `main`:** **media** — sin push directo, sin force-push, sin borrado; todo por
  PR; el check `build` debe pasar; auto-aprobación permitida (no exige segundo revisor).
- **Red de seguridad:** backup DB antes de deploy, health-check + rollback automático, alertas
  de caída por Telegram, y entorno de staging.
- **Alertas SOLO al owner (regla dura):** todas las notificaciones de deploy y de caída van a un
  único chat (`OWNER_CHAT_ID`), nunca a la pareja ni al hogar.
- **Mecanismo de deploy:** GitHub Actions → SSH → `deploy.sh` en el VPS (no Docker por ahora).
- **Notificación de éxito:** silenciosa por defecto (el owner solo es molestado ante problemas);
  el resultado siempre queda visible en GitHub Actions.

## Arquitectura / componentes

### A. Ramas y protección
- `main` protegida (media). Ramas de trabajo `feat/*`, `fix/*`.
- Limpiar la rama vieja `feat/dashboard-react`.

### B. CI — `.github/workflows/ci.yml` (en cada PR)
- Frontend: `npm ci`, `tsc --noEmit`, `npm run build`.
- Backend: `python -m compileall vps_current` + `pytest` (tests existentes: `visibility`,
  `calfeed`; se agregan los que surjan).
- Expone un status check llamado **`build`** → requerido por la protección de rama.

### C. `deploy/deploy.sh` (el corazón) — idempotente, con rollback
Vive versionado en el repo. Firma: `deploy.sh <ref> <entorno>` (`entorno` = `prod` | `staging`).
Pasos en orden:
1. **Backup**: `data.db` vía `backup_db.py`; guardar frontend actual como `juntu.prev` (mv).
2. `git fetch --tags && git checkout <ref>` en un **checkout limpio** `/home/emir/yumi`.
3. **Sync de código** a la run-dir con `rsync -a --delete` **excluyendo** runtime/secrets:
   `.env`, `data.db`, `venv/`, `backups/`, `vapid_private.pem`, `credenciales*`, `*.bak*`.
   (Esto de paso elimina los `apply_*.py`/`.bak` sueltos.)
4. `venv/bin/pip install -r requirements.txt` (idempotente; solo instala lo que cambió).
5. Copiar el frontend ya buildeado (artefacto de CI) a `/var/www/juntu`.
6. **Reiniciar** `asistente` + `asistente-web` (el esquema se auto-migra al bootear vía los
   `_ALTERS` idempotentes; no hay paso de migración separado).
7. **Health-check** (ver E). Si falla → **rollback**: volver al ref anterior + restaurar
   `juntu.prev`, reiniciar, y **avisar el problema al owner**. Si pasa → publicado (success
   silencioso).

`deploy.sh` registra "último ref bueno" para poder hacer rollback y para auditoría.

### D. Cómo CI entra al VPS
- **Clave SSH dedicada** de deploy → secrets de GitHub: `VPS_SSH_KEY`, `VPS_HOST`, `VPS_USER`.
  La pubkey se agrega a `~/.ssh/authorized_keys` del VPS (idealmente con `command=` restringido a
  `deploy.sh`).
- **sudoers acotado** (`/etc/sudoers.d/yumi-deploy`): `emir` corre SIN contraseña *solo*
  `systemctl restart asistente`, `systemctl restart asistente-web`,
  `systemctl restart asistente-staging`, `systemctl restart asistente-web-staging`,
  `systemctl reload caddy`. Nada más.
- **chown** de `/var/www/juntu` (y `yumi-landing`) a `emir:emir` (Caddy lee igual con `a+rX`) →
  el frontend se actualiza sin sudo.
- Secrets (`.env`, VAPID, tokens) **nunca** van a GitHub ni los toca el deploy.

### E. Health-check (`/api/health`)
- Se agrega endpoint liviano `GET /api/health` en `web.py` que devuelve `{ "ok": true }`
  (sin auth, sin tocar la DB pesada — a lo sumo un `SELECT 1`).
- Web sana = HTTP 200 en `/api/health`. Bot sano = `systemctl is-active asistente` = `active`
  y estable ~10s (no crash-loop).

### F. Versionado / releases — `.github/workflows/release.yml`
- `workflow_dispatch` con input `version` (semver, ej. `0.11.0`).
- Acciones: mover `CHANGELOG.md` `[Unreleased]` → `[vX.Y.Z]` con fecha; commit; crear tag
  `vX.Y.Z`; crear **GitHub Release** con esas notas.
- El tag dispara `.github/workflows/deploy-prod.yml` → `deploy.sh <tag> prod`.

### G. CD
- `.github/workflows/deploy-staging.yml`: on push a `main` → build frontend → subir artefacto →
  `ssh deploy.sh main staging`.
- `.github/workflows/deploy-prod.yml`: on tag `v*` → build frontend → subir artefacto →
  `ssh deploy.sh <tag> prod`.
- Ambos reportan resultado en GitHub Actions; `deploy.sh` avisa al owner solo ante fallo.

### H. Monitoreo / alertas (SOLO al owner) — `deploy/check.sh` + systemd timer
- `check.sh`: curl a `/api/health` (prod) + `systemctl is-active asistente`. Si algo está caído,
  manda **un** Telegram a `OWNER_CHAT_ID` usando el token del bot (de `.env`).
- `systemd timer` cada ~5 min. **Dedup por cambio de estado** (avisa al caer y al recuperarse;
  no spamea cada 5 min). Estado previo en un archivo (`/home/emir/asistente/.health_state`).

### I. Staging (la pieza más pesada — se decide al final)
- Servicios paralelos: `asistente-web-staging` (uvicorn `:8001`) y `asistente-staging` (bot con
  **token de Telegram propio** de BotFather — dos bots no pueden compartir token).
- **DB propia** (`data_staging.db`, copia inicial de prod) y `.env` propio
  (`.env.staging`) con `OWNER_CHAT_ID`, su token y su DB.
- Caddy: subdominio `staging.asistente.emir-maestu.site` (requiere registro DNS) → `/var/www/juntu-staging`
  + `reverse_proxy 127.0.0.1:8001`.
- Auto-deploy al mergear a `main` (`deploy-staging.yml`).

## Orden de implementación (fases)

- **Fase 0 — Reconciliar + base.** Diff de lo que corre en el VPS vs `vps_current/`; commitear
  drift; crear checkout limpio `/home/emir/yumi`; chown web roots; sudoers acotado;
  `/api/health`; `OWNER_CHAT_ID` en `.env`; escribir `deploy.sh`; probarlo a mano una vez
  (deploy de `main` a prod). Resultado: deploy de un comando, reproducible desde git.
- **Fase 1 — Protección de `main` + CI** (`ci.yml`, status check `build`, reglas de rama).
- **Fase 2 — CD a producción** (`deploy-prod.yml` con rollback + aviso al owner).
- **Fase 3 — Workflow de release** (`release.yml`: botón → changelog/tag/release).
- **Fase 4 — Monitoreo/alertas** (`check.sh` + systemd timer, solo al owner).
- **Fase 5 — Staging** (servicios + DB + bot token + DNS + `deploy-staging.yml`). Se decide si
  se ejecuta ya o se deja preparada.

## Acciones manuales del owner (guiadas paso a paso)
- Autenticar `gh` **o** configurar en la web de GitHub: 3 secrets (`VPS_SSH_KEY`, `VPS_HOST`,
  `VPS_USER`) + reglas de protección de `main`.
- Correr **una vez** en el VPS, con `sudo`: crear `/etc/sudoers.d/yumi-deploy` + `chown` de los
  web roots (comandos provistos listos).
- Para staging: crear bot nuevo en BotFather + registro DNS del subdominio.

## Restricciones de seguridad (heredadas, se mantienen)
- Secrets nunca se commitean (`.env`, `credenciales*`, `vapid_private.pem` están en `.gitignore`
  / `chmod 600`) y el deploy los excluye explícitamente.
- Validar cualquier migración destructiva sobre una **copia** de `data.db`, nunca la viva (acá el
  esquema se auto-migra con `_ALTERS` idempotentes; el backup pre-deploy es la red).
- El bot/web nunca devuelven data privada de otro miembro del hogar (modelo de privacidad ya
  vigente; este proyecto no lo toca).
- Rotación pendiente (operador): App Secret + token permanente de WhatsApp.

## No-objetivos (YAGNI por ahora)
- Dockerizar / registry / compose (se evalúa cuando un solo VPS no alcance).
- Segundo VPS dedicado.
- Aprobaciones de PR por segundo revisor.
- Blue/green o zero-downtime real (el restart de uvicorn es de <1s; aceptable).

## Riesgos / mitigaciones
- **`rsync --delete` borra de más** → lista de exclusión explícita + probar primero con
  `--dry-run` en Fase 0; backup de la run-dir antes del primer deploy automático.
- **Primer deploy clobbering drift no commiteado del VPS** → Fase 0 reconcilia y commitea el
  drift antes de automatizar.
- **Dos bots con mismo token (staging)** → token separado obligatorio; documentado.
- **Health-check falso-positivo deja prod abajo** → rollback automático + aviso al owner; el
  estado siempre visible en Actions.
