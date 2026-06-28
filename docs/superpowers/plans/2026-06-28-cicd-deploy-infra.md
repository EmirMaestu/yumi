# CI/CD + infra Yumi — Implementation Plan (Fases 0–4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pasar de deploy artesanal (scp + sudo a mano) a un flujo profesional: repo = espejo fiel de prod, `main` protegida con CI, deploy a producción al crear una release (con backup + health-check + rollback), versionado por releases y alertas de caída — todo notificando SOLO al owner.

**Architecture:** GitHub Actions → SSH → `deploy.sh` en el VPS. No se cambia cómo corre el proyecto (systemd `asistente` + `asistente-web` + Caddy). El repo `EmirMaestu/yumi` se vuelve el único source of truth; el VPS se actualiza desde git vía `rsync` con lista de exclusión para preservar runtime/secretos.

**Tech Stack:** Bash, GitHub Actions (YAML), systemd, Caddy, rsync, FastAPI (endpoint health), Vite/React build en CI.

**Spec:** `docs/superpowers/specs/2026-06-28-cicd-deploy-infra-design.md`

---

## Contexto crítico (leer antes de empezar)

- El repo `vps_current/` **NO** es un espejo completo del backend que corre. Hoy tiene 40 archivos `.bak` viejos y le **faltan ~37 archivos reales** que el server usa (`conversation.py`, `finance.py`, `fx.py`, `networth.py`, `proactive.py`, `recurrence.py`, `shopping.py`, `splits.py`, `streaks.py`, `trends.py`, `affordability.py`, `digest.py`, `ical.py`, `compare.py`, `extract_html.py`, `backup_db.py`, `requirements.txt`, etc.). **Por eso la Fase 0 es la más delicada: reconstruye el espejo completo ANTES de automatizar nada.** Si se corre `rsync --delete` sin reconciliar, se borra medio backend.
- `sudo` en el VPS **pide contraseña** (no passwordless). Los pasos con `sudo` los corre **el owner** (no el agente). Están marcados con **[OWNER]**.
- `gh` no está autenticado localmente. Los pasos de GitHub (secrets, branch protection) son **[OWNER]** (web de GitHub o `gh` tras `gh auth login`).
- Variable del token en `.env`: `TELEGRAM_TOKEN`. No existe `OWNER_CHAT_ID` → se agrega en Fase 0.
- Layout VPS: run-dir `/home/emir/asistente` (venv, `.env`, `data.db`, `backups/`), servicios `asistente` (bot `main.py`) y `asistente-web` (uvicorn `web:app` :8000), frontend en `/var/www/juntu` (root:root), landing en `/var/www/yumi-landing`.

## File Structure (qué se crea / modifica)

**Repo (nuevo):**
- `deploy/deploy.sh` — script de deploy idempotente con rollback (prod/staging).
- `deploy/check.sh` — chequeo de salud para el timer de monitoreo.
- `deploy/rsync-excludes.txt` — lista de exclusión (preserva runtime/secretos).
- `deploy/yumi-deploy.sudoers` — snippet sudoers acotado (referencia; lo instala el owner).
- `deploy/yumi-health.service` + `deploy/yumi-health.timer` — units del monitoreo.
- `deploy/README.md` — runbook (cómo deployar, rollback manual, troubleshooting).
- `.github/workflows/ci.yml` — checks en cada PR (status check `build`).
- `.github/workflows/deploy-prod.yml` — on tag `v*` → deploy a prod.
- `.github/workflows/release.yml` — manual dispatch → changelog/tag/release.
- `vps_current/.gitignore` — espejo del `.gitignore` del run-dir.

**Repo (modificar):**
- `vps_current/` — se le agregan los ~37 archivos reales faltantes y se borran los `.bak`.
- `vps_current/web.py` — endpoint `GET /api/health`.
- `CHANGELOG.md` — entrada de esta tanda.

**VPS (estado, no repo):**
- `/home/emir/yumi` — checkout limpio del repo (deploy source).
- `/home/emir/asistente/.env` — se le agrega `OWNER_CHAT_ID`.
- `/etc/sudoers.d/yumi-deploy` — [OWNER].
- `~/.ssh/authorized_keys` — pubkey de deploy [OWNER].

---

# FASE 0 — Reconciliar + base

## Task 0.1: Traer el source real del VPS al repo (reconstruir el espejo)

**Files:**
- Modify: `vps_current/` (agregar archivos reales, borrar `.bak`)
- Create: `vps_current/.gitignore`

- [ ] **Step 1: Backup del estado actual del repo vps_current (por las dudas)**

```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant
cp -r vps_current ../_vps_current_backup_pre_reconcile
```

- [ ] **Step 2: Borrar los .bak viejos del repo**

```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant
git rm -q vps_current/*.bak.* vps_current/*.bak 2>/dev/null; true
ls vps_current/*.bak* 2>/dev/null && echo "QUEDAN BAKS" || echo "OK sin baks"
```
Expected: `OK sin baks`

- [ ] **Step 3: Bajar el source real del VPS (solo código, excluyendo runtime/secretos/junk)**

Desde la PC. Trae todo `~/asistente/` salvo lo que es runtime, secretos o basura:
```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant
rsync -av --delete \
  --exclude='.git/' --exclude='.env' --exclude='.env.*' \
  --exclude='data.db' --exclude='data.db-*' --exclude='data.db.*' \
  --exclude='venv/' --exclude='backups/' --exclude='voice/' --exclude='photos/' \
  --exclude='plan/' --exclude='__pycache__/' --exclude='.pytest_cache/' \
  --exclude='*.pyc' --exclude='*.bak' --exclude='*.bak.*' --exclude='*.new' \
  --exclude='vapid_private.pem' --exclude='credenciales*' \
  --exclude=':USERPROFILEDownloads' --exclude='_smoke*' --exclude='apply_*' \
  --exclude='_verify_initdb.py' --exclude='_w*.py' --exclude='webapp/' \
  --exclude='.health_state' --exclude='.last_good_ref' \
  emir@217.76.48.219:'~/asistente/' vps_current/
```
Nota: este `--delete` es contra `vps_current/` LOCAL (lo hace espejo del server), no contra el server.

- [ ] **Step 4: Verificar que están los archivos clave que faltaban**

```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant
for f in conversation.py finance.py fx.py networth.py proactive.py recurrence.py \
         shopping.py splits.py streaks.py trends.py backup_db.py requirements.txt \
         main.py web.py crud_v2.py calfeed.py visibility.py; do
  test -f vps_current/$f && echo "OK $f" || echo "FALTA $f"
done
```
Expected: todos `OK`.

- [ ] **Step 5: Confirmar que NO se colaron secretos/runtime**

```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant
ls vps_current/ | grep -E '^\.env$|data\.db|vapid_private|credenciales|^venv$' && echo "PELIGRO: secreto/runtime" || echo "OK limpio"
```
Expected: `OK limpio`

- [ ] **Step 6: Crear `vps_current/.gitignore` (espejo del run-dir)**

```
# datos y secretos
data.db
data.db-shm
data.db-wal
data.db.*
.env
.env.*
vapid_private.pem
credenciales*
# media temporal
voice/
photos/
# backups y artefactos
backups/
webapp/
*.bak
*.bak.*
*.new
# estado de deploy
.health_state
.last_good_ref
# python
__pycache__/
*.pyc
.pytest_cache/
venv/
```

- [ ] **Step 7: Commit**

```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant
git add vps_current
git commit -m "chore(reconcile): vps_current = espejo completo del backend en prod (+ borra .bak)"
```

## Task 0.2: Endpoint de health en la web

**Files:**
- Modify: `vps_current/web.py`
- Test: `vps_current/tests/test_health.py`

- [ ] **Step 1: Escribir el test (TDD)**

```python
# vps_current/tests/test_health.py
from fastapi.testclient import TestClient
import web

def test_health_ok():
    c = TestClient(web.app)
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json().get("ok") is True
```

- [ ] **Step 2: Correr el test, verificar que falla**

Run: `cd vps_current && python -m pytest tests/test_health.py -v`
Expected: FAIL (404 / no existe la ruta).

- [ ] **Step 3: Agregar la ruta en `web.py`**

Buscar la línea donde se define `app = FastAPI(...)` y, debajo de las rutas existentes, agregar (no requiere auth, no toca la DB pesada):
```python
@app.get("/api/health")
def health():
    return {"ok": True}
```

- [ ] **Step 4: Correr el test, verificar que pasa**

Run: `cd vps_current && python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vps_current/web.py vps_current/tests/test_health.py
git commit -m "feat(web): endpoint GET /api/health para health-check del deploy"
```

## Task 0.3: Lista de exclusión del deploy (rsync VPS)

**Files:**
- Create: `deploy/rsync-excludes.txt`

- [ ] **Step 1: Crear el archivo** (lo que el deploy debe PRESERVAR en el run-dir)

```
.git/
.env
.env.*
data.db
data.db-shm
data.db-wal
data.db.*
venv/
backups/
voice/
photos/
plan/
__pycache__/
.pytest_cache/
*.pyc
vapid_private.pem
credenciales*
.health_state
.last_good_ref
webapp/
```

- [ ] **Step 2: Commit**

```bash
git add deploy/rsync-excludes.txt
git commit -m "chore(deploy): lista de exclusión rsync (preserva runtime/secretos)"
```

## Task 0.4: `deploy.sh` (corazón del deploy, con rollback)

**Files:**
- Create: `deploy/deploy.sh`

- [ ] **Step 1: Escribir el script**

```bash
#!/usr/bin/env bash
# deploy.sh <ref> <env>
#   ref: tag/branch/commit a desplegar (ej: v0.11.0 | main)
#   env: prod | staging
set -euo pipefail

REF="${1:?uso: deploy.sh <ref> <env>}"
ENVN="${2:-prod}"

REPO="/home/emir/yumi"
RUN="/home/emir/asistente"
EXCLUDES="$REPO/deploy/rsync-excludes.txt"
TS="$(date +%Y%m%d-%H%M%S)"

if [ "$ENVN" = "staging" ]; then
  WEBROOT="/var/www/juntu-staging"; HEALTH="http://127.0.0.1:8001/api/health"
  SVC_BOT="asistente-staging"; SVC_WEB="asistente-web-staging"
else
  WEBROOT="/var/www/juntu"; HEALTH="http://127.0.0.1:8000/api/health"
  SVC_BOT="asistente"; SVC_WEB="asistente-web"
fi

log(){ echo "[deploy $TS][$ENVN] $*"; }

notify_owner(){ # $1 = texto. Solo al owner, vía bot. Nunca falla el deploy por esto.
  set +e
  local TOKEN CHAT
  TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$RUN/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"'"' ')"
  CHAT="$(grep -E '^OWNER_CHAT_ID=' "$RUN/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"'"' ')"
  if [ -n "$TOKEN" ] && [ -n "$CHAT" ]; then
    curl -s -m 10 "https://api.telegram.org/bot${TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${CHAT}" --data-urlencode "text=$1" >/dev/null
  fi
  set -e
}

healthy(){ # web 200 en /api/health  +  bot active y estable
  curl -fsS -m 8 "$HEALTH" >/dev/null 2>&1 || return 1
  systemctl is-active --quiet "$SVC_BOT" || return 1
  sleep 8
  systemctl is-active --quiet "$SVC_BOT" || return 1
  curl -fsS -m 8 "$HEALTH" >/dev/null 2>&1 || return 1
  return 0
}

restart_services(){ sudo systemctl restart "$SVC_BOT" "$SVC_WEB"; }

PREV_REF="$(cat "$RUN/.last_good_ref" 2>/dev/null || echo '')"

log "ref=$REF prev=${PREV_REF:-none}"

# 1) Backup DB + frontend actual
log "backup DB"
( cd "$RUN" && "$RUN/venv/bin/python" backup_db.py ) || cp -a "$RUN/data.db" "$RUN/backups/data.db.$TS" 2>/dev/null || true
if [ -d "$WEBROOT" ]; then rm -rf "${WEBROOT}.prev"; cp -a "$WEBROOT" "${WEBROOT}.prev"; fi

# 2) Checkout del ref pedido
log "git checkout $REF"
git -C "$REPO" fetch --all --tags --prune
git -C "$REPO" checkout -f "$REF"

# 3) Sync de código (preserva runtime/secretos)
log "rsync código"
rsync -a --delete --exclude-from="$EXCLUDES" "$REPO/vps_current/" "$RUN/"

# 4) Dependencias (idempotente)
if [ -f "$RUN/requirements.txt" ]; then
  log "pip install"
  "$RUN/venv/bin/pip" install -q -r "$RUN/requirements.txt"
fi

# 5) Frontend (artefacto buildeado por CI, dejado en $REPO/web-react/dist)
if [ -d "$REPO/web-react/dist" ]; then
  log "deploy frontend -> $WEBROOT"
  rm -rf "${WEBROOT}.new"; cp -a "$REPO/web-react/dist" "${WEBROOT}.new"
  chmod -R a+rX "${WEBROOT}.new"
  rm -rf "$WEBROOT"; mv "${WEBROOT}.new" "$WEBROOT"
fi

# 6) Restart
log "restart"
restart_services

# 7) Health-check + rollback
if healthy; then
  echo "$REF" > "$RUN/.last_good_ref"
  log "OK saludable"
  exit 0
fi

log "FALLO health-check -> rollback"
if [ -d "${WEBROOT}.prev" ]; then rm -rf "$WEBROOT"; mv "${WEBROOT}.prev" "$WEBROOT"; fi
if [ -n "$PREV_REF" ]; then
  git -C "$REPO" checkout -f "$PREV_REF" || true
  rsync -a --delete --exclude-from="$EXCLUDES" "$REPO/vps_current/" "$RUN/"
  [ -f "$RUN/requirements.txt" ] && "$RUN/venv/bin/pip" install -q -r "$RUN/requirements.txt" || true
fi
restart_services
notify_owner "❌ Deploy $ENVN de $REF falló el health-check. Rollback a ${PREV_REF:-versión anterior}. Revisá: journalctl -u $SVC_WEB -n 50"
exit 1
```

- [ ] **Step 2: Hacerlo ejecutable y commit**

```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant
git add deploy/deploy.sh
git update-index --chmod=+x deploy/deploy.sh
git commit -m "feat(deploy): deploy.sh idempotente con backup, rollback y aviso al owner"
```

## Task 0.5: [OWNER] Preparar el VPS (checkout, sudoers, chown, OWNER_CHAT_ID)

**Files:**
- Create: `deploy/yumi-deploy.sudoers`

- [ ] **Step 1: Crear el snippet sudoers en el repo (referencia)**

```
# /etc/sudoers.d/yumi-deploy  — permite a emir reiniciar SOLO estos servicios sin password
emir ALL=(root) NOPASSWD: /bin/systemctl restart asistente, /bin/systemctl restart asistente-web, /bin/systemctl restart asistente-staging, /bin/systemctl restart asistente-web-staging, /bin/systemctl reload caddy
```
Commit:
```bash
git add deploy/yumi-deploy.sudoers
git commit -m "chore(deploy): snippet sudoers acotado para restart sin password"
```

- [ ] **Step 2: [OWNER] Clonar el repo como checkout de deploy en el VPS**

```bash
ssh emir@217.76.48.219 'git clone https://github.com/EmirMaestu/yumi.git ~/yumi && cd ~/yumi && git checkout main'
```
Expected: clona sin error. (Si el repo es privado, configurar antes un deploy key o `gh auth`.)

- [ ] **Step 3: [OWNER] Instalar el sudoers acotado (con visudo, valida sintaxis)**

```bash
ssh -t emir@217.76.48.219 'sudo install -m 0440 ~/yumi/deploy/yumi-deploy.sudoers /etc/sudoers.d/yumi-deploy && sudo visudo -cf /etc/sudoers.d/yumi-deploy'
```
Expected: `/etc/sudoers.d/yumi-deploy: parsed OK`

- [ ] **Step 4: [OWNER] Verificar restart sin password**

```bash
ssh emir@217.76.48.219 'sudo -n systemctl restart asistente-web && echo RESTART_OK'
```
Expected: `RESTART_OK` (sin pedir contraseña).

- [ ] **Step 5: [OWNER] Chown del web root a emir (deploy sin sudo del frontend)**

```bash
ssh -t emir@217.76.48.219 'sudo chown -R emir:emir /var/www/juntu /var/www/yumi-landing && echo CHOWN_OK'
```
Expected: `CHOWN_OK`. (Caddy sigue leyendo: el deploy hace `chmod a+rX`.)

- [ ] **Step 6: [OWNER] Obtener tu chat_id de Telegram y agregarlo al `.env`**

Mandale `/start` o cualquier mensaje al bot y luego:
```bash
ssh emir@217.76.48.219 'source ~/asistente/.env; curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/getUpdates" | python3 -c "import sys,json;[print(u[\"message\"][\"chat\"][\"id\"], u[\"message\"][\"chat\"].get(\"username\")) for u in json.load(sys.stdin).get(\"result\",[])]"'
```
Tomar TU chat_id y agregarlo (reemplazar `NNNN`):
```bash
ssh emir@217.76.48.219 'grep -q "^OWNER_CHAT_ID=" ~/asistente/.env || echo "OWNER_CHAT_ID=NNNN" >> ~/asistente/.env; grep OWNER_CHAT_ID ~/asistente/.env'
```
Expected: imprime `OWNER_CHAT_ID=NNNN`.

## Task 0.6: Primer deploy MANUAL (dry-run primero) — el momento de la verdad

- [ ] **Step 1: [OWNER] DRY-RUN del rsync de código (NADA se escribe, solo se lista)**

```bash
ssh emir@217.76.48.219 'cd ~/yumi && git fetch --all -q && git checkout -f main -q && rsync -a --delete --dry-run --itemize-changes --exclude-from=deploy/rsync-excludes.txt vps_current/ ~/asistente/ | grep -E "^\*deleting|^>f" | head -80'
```
**REVISAR la salida**: las líneas `*deleting` solo deben ser junk (`apply_*.py`, `_smoke*.py`, `*.bak*`, `:USERPROFILEDownloads`, `Caddyfile.new`, etc.). Si aparece un `*deleting` de un archivo de código real o de runtime → **PARAR** y agregarlo al repo o a los excludes antes de seguir.

- [ ] **Step 2: [OWNER] Backup completo del run-dir (red extra antes del primer deploy real)**

```bash
ssh emir@217.76.48.219 'tar czf ~/asistente_runtime_backup_pre_cicd.tgz -C ~ asistente --exclude=asistente/venv && ls -lh ~/asistente_runtime_backup_pre_cicd.tgz'
```

- [ ] **Step 3: [OWNER] Build del frontend para el primer deploy**

Desde la PC (CI lo hará después; ahora a mano para la primera vez):
```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant/web-react && npm ci && npm run build
ssh emir@217.76.48.219 'rm -rf ~/yumi/web-react/dist'
scp -q -r dist emir@217.76.48.219:'~/yumi/web-react/dist'
```

- [ ] **Step 4: [OWNER] Correr el deploy real a prod**

```bash
ssh emir@217.76.48.219 'cd ~/yumi && bash deploy/deploy.sh main prod; echo "exit=$?"'
```
Expected: `[deploy ...][prod] OK saludable` y `exit=0`.

- [ ] **Step 5: [OWNER] Verificar la app en vivo**

```bash
curl -fsS https://asistente.emir-maestu.site/api/health && echo "  <- web OK"
ssh emir@217.76.48.219 'systemctl is-active asistente asistente-web'
```
Expected: `{"ok":true} <- web OK` y `active` / `active`. Probar el bot con un mensaje real.

- [ ] **Step 6: [OWNER] Verificar limpieza del run-dir**

```bash
ssh emir@217.76.48.219 'ls ~/asistente | grep -E "apply_|\.bak|_smoke" | wc -l'
```
Expected: `0` (el junk se limpió). Confirmar que `.env`, `data.db`, `venv` siguen ahí:
```bash
ssh emir@217.76.48.219 'ls -d ~/asistente/.env ~/asistente/data.db ~/asistente/venv'
```

---

# FASE 1 — Protección de main + CI

## Task 1.1: Workflow de CI (checks en PR)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Crear el workflow**

```yaml
name: build
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
jobs:
  frontend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: web-react } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'npm', cache-dependency-path: web-react/package-lock.json }
      - run: npm ci
      - run: npx tsc --noEmit
      - run: npm run build
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: python -m pip install -r vps_current/requirements.txt
      - run: python -m compileall -q vps_current
      - run: cd vps_current && python -m pytest -q
```

- [ ] **Step 2: Commit y push en una rama de prueba**

```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant
git checkout -b chore/ci
git add .github/workflows/ci.yml
git commit -m "ci: build + tests en cada PR (frontend tsc/build, backend compileall/pytest)"
git push -u origin chore/ci
```

- [ ] **Step 3: [OWNER] Abrir el PR y verificar que el job `build` corre**

```bash
gh pr create --fill   # o por la web
```
Expected: en el PR aparecen los checks `build / frontend` y `build / backend` y pasan en verde. (Si `pytest` falla por imports que requieren `.env`, ajustar los tests para que no dependan de secrets — los de `visibility`/`calfeed`/`health` no deberían.)

## Task 1.2: [OWNER] Secrets de deploy en GitHub

- [ ] **Step 1: Generar una clave SSH dedicada de deploy (en la PC)**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/yumi_deploy -N "" -C "github-actions-deploy"
```

- [ ] **Step 2: [OWNER] Autorizar la pubkey en el VPS**

```bash
ssh-copy-id -i ~/.ssh/yumi_deploy.pub emir@217.76.48.219
# verificar:
ssh -i ~/.ssh/yumi_deploy emir@217.76.48.219 'echo SSH_DEPLOY_OK'
```
Expected: `SSH_DEPLOY_OK`

- [ ] **Step 3: [OWNER] Cargar los secrets en GitHub**

```bash
gh secret set VPS_SSH_KEY < ~/.ssh/yumi_deploy
gh secret set VPS_HOST --body "217.76.48.219"
gh secret set VPS_USER --body "emir"
gh secret list
```
Expected: lista `VPS_SSH_KEY`, `VPS_HOST`, `VPS_USER`.

## Task 1.3: [OWNER] Activar la protección de main (media)

- [ ] **Step 1: Aplicar las reglas vía gh API**

```bash
gh api -X PUT repos/EmirMaestu/yumi/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=build / frontend' \
  -f 'required_status_checks[contexts][]=build / backend' \
  -f 'enforce_admins=false' \
  -f 'required_pull_request_reviews[required_approving_review_count]=0' \
  -f 'restrictions=' \
  -F 'allow_force_pushes=false' \
  -F 'allow_deletions=false'
```
(Alternativa: web → Settings → Branches → Add rule para `main`: require PR, require status checks `build / frontend` + `build / backend`, block force-push, block deletions, no exigir aprobaciones.)

- [ ] **Step 2: Verificar**

```bash
gh api repos/EmirMaestu/yumi/branches/main/protection --jq '{checks:.required_status_checks.contexts, force:.allow_force_pushes.enabled, del:.allow_deletions.enabled}'
```
Expected: contexts con los dos `build`, `force:false`, `del:false`.

- [ ] **Step 3: Mergear el PR de CI** (ya con la rama protegida y checks en verde).

---

# FASE 2 — CD a producción

## Task 2.1: Workflow de deploy a prod (on tag)

**Files:**
- Create: `.github/workflows/deploy-prod.yml`

- [ ] **Step 1: Crear el workflow**

```yaml
name: deploy-prod
on:
  push:
    tags: ['v*']
concurrency: { group: deploy-prod, cancel-in-progress: false }
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      # build frontend
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'npm', cache-dependency-path: web-react/package-lock.json }
      - run: cd web-react && npm ci && npm run build
      # ssh setup
      - name: SSH key
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.VPS_SSH_KEY }}" > ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/id_ed25519
          ssh-keyscan -H "${{ secrets.VPS_HOST }}" >> ~/.ssh/known_hosts 2>/dev/null
      # subir el dist buildeado al checkout del VPS
      - name: Upload frontend dist
        run: |
          ssh -i ~/.ssh/id_ed25519 ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} 'rm -rf ~/yumi/web-react/dist && mkdir -p ~/yumi/web-react'
          scp -i ~/.ssh/id_ed25519 -r web-react/dist ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }}:'~/yumi/web-react/dist'
      # ejecutar deploy.sh con el tag
      - name: Deploy
        run: |
          ssh -i ~/.ssh/id_ed25519 ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} \
            "cd ~/yumi && git fetch --all --tags -q && bash deploy/deploy.sh '${{ github.ref_name }}' prod"
```

- [ ] **Step 2: Commit en una rama + PR + merge**

```bash
git checkout -b ci/deploy-prod
git add .github/workflows/deploy-prod.yml
git commit -m "ci: deploy a producción al pushear un tag v* (build + ssh + deploy.sh con rollback)"
git push -u origin ci/deploy-prod
gh pr create --fill
```

## Task 2.2: Probar el CD con un tag de prueba

- [ ] **Step 1: [OWNER] Tras mergear, crear un tag de prueba y verificar el deploy automático**

```bash
git checkout main && git pull
git tag v0.10.1 -m "prueba CD"
git push origin v0.10.1
gh run watch
```
Expected: el workflow `deploy-prod` corre, buildea, deploya, el job termina verde, `https://asistente.emir-maestu.site/api/health` responde.

- [ ] **Step 2: [OWNER] Probar el rollback (deliberado)**

Romper algo temporalmente para forzar el fallo de health-check NO es necesario en prod; en su lugar, confiar en el rollback ya probado en staging (Fase 5). Documentar en `deploy/README.md` el rollback manual:
```bash
ssh emir@217.76.48.219 'cd ~/yumi && bash deploy/deploy.sh <TAG_ANTERIOR> prod'
```

## Task 2.3: Runbook de deploy

**Files:**
- Create: `deploy/README.md`

- [ ] **Step 1: Escribir el runbook** (cómo se publica, cómo se hace rollback, dónde ver logs)

```markdown
# Deploy runbook (Yumi)

## Publicar a producción
1. Mergeá tus PRs a `main` (CI en verde).
2. Corré el workflow **release** (Actions → release → Run) y elegí la versión.
3. Eso crea el tag `vX.Y.Z` → dispara `deploy-prod` → deploy.sh con backup + health-check + rollback.

## Rollback manual
ssh emir@217.76.48.219 'cd ~/yumi && bash deploy/deploy.sh <tag_anterior> prod'

## Logs
- Deploy: GitHub → Actions → deploy-prod.
- App: journalctl -u asistente -n 80   /   journalctl -u asistente-web -n 80

## Qué preserva el deploy
.env, data.db(*), venv, backups/, voice/, photos/, vapid_private.pem, credenciales* (ver deploy/rsync-excludes.txt)
```

- [ ] **Step 2: Commit**

```bash
git add deploy/README.md
git commit -m "docs(deploy): runbook (publicar, rollback, logs)"
```

---

# FASE 3 — Workflow de release (botón + versionado)

## Task 3.1: Workflow de release

**Files:**
- Create: `.github/workflows/release.yml`

**Decisión de diseño:** el workflow **NO commitea a `main`** (la protección exige PR, así que un `git push origin main` desde el Action fallaría). Por eso el roll del CHANGELOG (`[Unreleased]` → `[X.Y.Z]`) se hace **a mano en el último PR antes de releasear**, y el workflow solo crea el **tag** + la **GitHub Release** a partir del estado actual de `main`. El tag dispara `deploy-prod`. Resultado: el botón "release" = tag + Release + deploy, sin tocar `main`.

- [ ] **Step 1: Crear el workflow (versión final)**

```yaml
name: release
on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Versión semver sin la v (ej: 0.11.0)'
        required: true
permissions: { contents: write }
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0, ref: main }
      - name: Tag + GitHub Release (notas = sección del CHANGELOG)
        run: |
          V="${{ github.event.inputs.version }}"
          git tag "v$V" -m "v$V" && git push origin "v$V"
          awk "/^## \\[$V\\]/{f=1;next} /^## \\[/{if(f)exit} f" CHANGELOG.md > /tmp/notes.md
          gh release create "v$V" --title "v$V" --notes-file /tmp/notes.md
        env: { GH_TOKEN: '${{ github.token }}' }
```

- [ ] **Step 2: Commit (rama + PR + merge)**

```bash
git checkout -b ci/release
git add .github/workflows/release.yml
git commit -m "ci: workflow release (botón -> tag + GitHub Release -> dispara deploy-prod)"
git push -u origin ci/release
gh pr create --fill
```

## Task 3.2: Documentar el flujo de versionado

- [ ] **Step 1: Agregar al `deploy/README.md` la convención**

Editar `deploy/README.md` agregando:
```markdown
## Versionado
- Antes de releasear, en el último PR: mover en CHANGELOG.md lo de `## [Unreleased]` a `## [X.Y.Z] - YYYY-MM-DD`.
- Actions → release → Run → escribir `X.Y.Z`. Crea el tag, la GitHub Release (notas = esa sección) y dispara el deploy a prod.
- SemVer: MINOR por tanda de features, PATCH por fixes.
```
Commit:
```bash
git add deploy/README.md && git commit -m "docs(deploy): convención de versionado/release"
```

---

# FASE 4 — Monitoreo / alertas (SOLO al owner)

## Task 4.1: `check.sh` (chequeo de salud con dedup)

**Files:**
- Create: `deploy/check.sh`

- [ ] **Step 1: Escribir el script**

```bash
#!/usr/bin/env bash
# check.sh — pinguea prod; avisa al owner por Telegram SOLO al cambiar de estado.
set -uo pipefail
RUN="/home/emir/asistente"
HEALTH="http://127.0.0.1:8000/api/health"
STATE="$RUN/.health_state"

ok=1
curl -fsS -m 8 "$HEALTH" >/dev/null 2>&1 || ok=0
systemctl is-active --quiet asistente || ok=0

prev="$(cat "$STATE" 2>/dev/null || echo up)"
now=$([ "$ok" = 1 ] && echo up || echo down)
echo "$now" > "$STATE"

[ "$now" = "$prev" ] && exit 0   # sin cambio -> no spamear

TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$RUN/.env" | head -1 | cut -d= -f2- | tr -d '"'"'"'"' ')"
CHAT="$(grep -E '^OWNER_CHAT_ID=' "$RUN/.env" | head -1 | cut -d= -f2- | tr -d '"'"'"'"' ')"
if [ "$now" = down ]; then MSG="🔴 Yumi CAÍDA: la web/bot no responde. journalctl -u asistente-web -n 50"
else MSG="🟢 Yumi se recuperó."; fi
[ -n "$TOKEN" ] && [ -n "$CHAT" ] && curl -s -m 10 \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${CHAT}" --data-urlencode "text=${MSG}" >/dev/null
```

- [ ] **Step 2: Commit**

```bash
cd /c/Users/emirm/OneDrive/Desktop/asistant
git add deploy/check.sh
git update-index --chmod=+x deploy/check.sh
git commit -m "feat(monitor): check.sh — alerta de caída al owner con dedup por estado"
```

## Task 4.2: systemd timer del monitoreo

**Files:**
- Create: `deploy/yumi-health.service`, `deploy/yumi-health.timer`

- [ ] **Step 1: Crear los units**

`deploy/yumi-health.service`:
```ini
[Unit]
Description=Yumi health check
[Service]
Type=oneshot
ExecStart=/bin/bash /home/emir/yumi/deploy/check.sh
User=emir
```
`deploy/yumi-health.timer`:
```ini
[Unit]
Description=Yumi health check cada 5 min
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
```

- [ ] **Step 2: Commit**

```bash
git add deploy/yumi-health.service deploy/yumi-health.timer
git commit -m "feat(monitor): systemd timer (cada 5 min) para el health check"
```

## Task 4.3: [OWNER] Instalar y activar el timer en el VPS

- [ ] **Step 1: [OWNER] Instalar units y activar** (tras el deploy que ya dejó los archivos en `~/yumi`)

```bash
ssh -t emir@217.76.48.219 'sudo cp ~/yumi/deploy/yumi-health.service /etc/systemd/system/ && sudo cp ~/yumi/deploy/yumi-health.timer /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now yumi-health.timer && systemctl list-timers yumi-health.timer --no-pager'
```
Expected: el timer aparece listado y activo.

- [ ] **Step 2: [OWNER] Probar la alerta (forzar down y restaurar)**

```bash
ssh emir@217.76.48.219 'echo up > ~/asistente/.health_state; sudo systemctl stop asistente-web; bash ~/yumi/deploy/check.sh; sleep 1; sudo systemctl start asistente-web; bash ~/yumi/deploy/check.sh'
```
Expected: te llega 🔴 (caída) y luego 🟢 (recuperación) a TU Telegram, y a nadie más.

---

## CHANGELOG

- [ ] Agregar a `CHANGELOG.md` (`[Unreleased]` → `### Added`):
```
- **CI/CD + infra.** Deploy automatizado por GitHub Actions: PRs con checks (build+tests), `main` protegida, deploy a producción al crear una release (con backup de DB, health-check y rollback automático), versionado por releases, y monitoreo con alerta de caída por Telegram (solo al owner). El repo es ahora el único source of truth; el VPS se actualiza desde git. Scripts en `deploy/` y workflows en `.github/workflows/`.
```

---

## Self-review (cobertura del spec)

- Disparador deploy = release/tag → **Task 2.1 / 3.1** ✓
- Protección media de main → **Task 1.3** ✓
- Backup DB antes de deploy → **deploy.sh paso 1** ✓
- Health-check + rollback → **deploy.sh pasos 6–7** ✓
- Alertas de caída solo-owner → **Task 4.1–4.3** ✓
- Reconciliar repo↔VPS + limpieza → **Task 0.1, 0.6** ✓
- CI (status check `build`) → **Task 1.1** ✓
- Versionado/changelog/release → **Task 3.1–3.2** ✓
- sudoers acotado + chown + SSH key → **Task 0.5, 1.2** ✓
- `/api/health` → **Task 0.2** ✓
- Staging → **NO en este plan** (Fase 5, plan aparte: requiere bot token nuevo + DNS + 2da DB).

## Notas de ejecución
- Pasos **[OWNER]**: requieren `sudo` o acceso a GitHub que el agente no tiene → coordinarlos con Emir; el agente prepara los archivos y le pasa los comandos listos.
- Orden estricto: la **Fase 0 es bloqueante** (sin el espejo reconciliado, el resto es peligroso). El dry-run del Task 0.6 Step 1 es el gate de seguridad — no avanzar si borra código real.
- Staging (Fase 5) se planifica por separado una vez que 0–4 estén probadas.
```
