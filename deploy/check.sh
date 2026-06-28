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

TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$RUN/.env" | head -1 | cut -d= -f2- | tr -d '"'\'' ')"
CHAT="$(grep -E '^OWNER_CHAT_ID=' "$RUN/.env" | head -1 | cut -d= -f2- | tr -d '"'\'' ')"
if [ "$now" = down ]; then
  MSG="🔴 Yumi CAÍDA: la web/bot no responde. journalctl -u asistente-web -n 50"
else
  MSG="🟢 Yumi se recuperó."
fi
[ -n "$TOKEN" ] && [ -n "$CHAT" ] && curl -s -m 10 \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${CHAT}" --data-urlencode "text=${MSG}" >/dev/null
