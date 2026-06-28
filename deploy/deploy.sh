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
# Backup del frontend en el home de emir (NO en /var/www, que es de root, ni en
# $RUN, que el rsync de código limpiaría).
WEBPREV="/home/emir/.yumi-webroot-prev-$ENVN"

log(){ echo "[deploy $TS][$ENVN] $*"; }

notify_owner(){ # $1 = texto. Solo al owner, vía bot. Nunca falla el deploy por esto.
  set +e
  local TOKEN CHAT
  TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$RUN/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'\'' ')"
  CHAT="$(grep -E '^OWNER_CHAT_ID=' "$RUN/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'\'' ')"
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

# Reiniciar de a UNO: el sudoers acotado permite cada servicio por separado,
# no el comando combinado. -n nunca pide contraseña (falla rápido si no matchea).
restart_services(){ sudo -n systemctl restart "$SVC_BOT"; sudo -n systemctl restart "$SVC_WEB"; }

PREV_REF="$(cat "$RUN/.last_good_ref" 2>/dev/null || echo '')"

log "ref=$REF prev=${PREV_REF:-none}"

# 1) Backup DB + frontend actual
log "backup DB"
( cd "$RUN" && "$RUN/venv/bin/python" backup_db.py ) || cp -a "$RUN/data.db" "$RUN/backups/data.db.$TS" 2>/dev/null || true
if [ -d "$WEBROOT" ]; then rm -rf "$WEBPREV"; cp -a "$WEBROOT" "$WEBPREV"; fi

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

# 5) Frontend (artefacto buildeado por CI, en $REPO/web-react/dist).
# Sincronizamos el CONTENIDO dentro de $WEBROOT (emir es dueño del contenido); no
# creamos/renombramos entradas en /var/www (eso es de root).
if [ -d "$REPO/web-react/dist" ]; then
  log "deploy frontend -> $WEBROOT"
  mkdir -p "$WEBROOT"
  rsync -a --delete "$REPO/web-react/dist/" "$WEBROOT/"
  chmod -R a+rX "$WEBROOT"
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
if [ -d "$WEBPREV" ]; then rsync -a --delete "$WEBPREV/" "$WEBROOT/"; chmod -R a+rX "$WEBROOT"; fi
if [ -n "$PREV_REF" ]; then
  git -C "$REPO" checkout -f "$PREV_REF" || true
  rsync -a --delete --exclude-from="$EXCLUDES" "$REPO/vps_current/" "$RUN/"
  [ -f "$RUN/requirements.txt" ] && "$RUN/venv/bin/pip" install -q -r "$RUN/requirements.txt" || true
fi
restart_services
notify_owner "❌ Deploy $ENVN de $REF falló el health-check. Rollback a ${PREV_REF:-versión anterior}. Revisá: journalctl -u $SVC_WEB -n 50"
exit 1
