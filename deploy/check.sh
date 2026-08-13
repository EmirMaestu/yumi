#!/usr/bin/env bash
# check.sh — pinguea prod y avisa al owner por Telegram SOLO al cambiar de estado.
#
# Robusto contra flapeo:
#  - Histéresis: declara "caído" recién tras THRESHOLD chequeos fallidos seguidos
#    (un blip o un reinicio puntual NO dispara alerta).
#  - Detección de crash-loop: si el bot reinició varias veces entre chequeos, cuenta
#    como caído aunque justo lo agarre "active" (así no se esconde un crash-loop).
#  - Se recupera apenas responde de nuevo.
set -uo pipefail
RUN="/home/emir/asistente"
HEALTH="http://127.0.0.1:8000/api/health"
STATE="$RUN/.health_state"
FAILS="$RUN/.health_fails"
RSTATE="$RUN/.health_restarts"
THRESHOLD=2   # 2 fallas seguidas (~10 min con el timer de 5 min) antes de avisar caída

web_ok=1; bot_ok=1
curl -fsS -m 8 "$HEALTH" >/dev/null 2>&1 || web_ok=0
systemctl is-active --quiet asistente || bot_ok=0

# crash-loop: NRestarts saltó mucho desde el último chequeo -> no está sano
restarts="$(systemctl show asistente -p NRestarts --value 2>/dev/null || echo 0)"
last_restarts="$(cat "$RSTATE" 2>/dev/null || echo "$restarts")"
echo "$restarts" > "$RSTATE"
[ "$((restarts - last_restarts))" -gt 2 ] && bot_ok=0

ok=1; { [ "$web_ok" = 1 ] && [ "$bot_ok" = 1 ]; } || ok=0

# contador de fallas consecutivas (histéresis)
fails="$(cat "$FAILS" 2>/dev/null || echo 0)"
if [ "$ok" = 1 ]; then fails=0; else fails=$((fails + 1)); fi
echo "$fails" > "$FAILS"

# estado DECLARADO: caído solo tras THRESHOLD fallas seguidas
now=up
[ "$fails" -ge "$THRESHOLD" ] && now=down

prev="$(cat "$STATE" 2>/dev/null || echo up)"
echo "$now" > "$STATE"
[ "$now" = "$prev" ] && exit 0   # sin cambio de estado declarado -> no spamear

TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$RUN/.env" | head -1 | cut -d= -f2- | tr -d '"'\'' ')"
CHAT="$(grep -E '^OWNER_CHAT_ID=' "$RUN/.env" | head -1 | cut -d= -f2- | tr -d '"'\'' ')"
if [ "$now" = down ]; then
  svc="asistente"; [ "$web_ok" = 0 ] && svc="asistente-web"
  MSG="🔴 Yumi CAÍDA (web:${web_ok} bot:${bot_ok}, ${fails} chequeos seguidos). Revisá: journalctl -u ${svc} -n 50"
else
  MSG="🟢 Yumi se recuperó."
fi
[ -n "$TOKEN" ] && [ -n "$CHAT" ] && curl -s -m 10 \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${CHAT}" --data-urlencode "text=${MSG}" >/dev/null
