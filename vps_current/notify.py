"""Lógica PURA de entrega proactiva multicanal (Telegram + WhatsApp oficial).
Sin dependencias pesadas (solo datetime) → testeable en aislamiento. El envío real
(async, red) vive en main.notify_user, que usa estas funciones para decidir."""
from datetime import datetime


def wa_window_open(last_inbound_str, now_utc=None):
    """True si el usuario de WhatsApp escribió hace <24h (ventana de servicio abierta →
    se puede mandar TEXTO LIBRE gratis). `last_inbound_str` = users.wa_last_inbound_at
    (UTC 'YYYY-MM-DD HH:MM:SS'). now_utc inyectable para tests."""
    if not last_inbound_str:
        return False
    now_utc = now_utc or datetime.utcnow()
    s = str(last_inbound_str).replace("T", " ")[:19]
    try:
        last = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return False
    return 0 <= (now_utc - last).total_seconds() < 24 * 3600


def delivery_plan(user_row, now_utc=None, allow_template=True):
    """Decide canal(es) y modo. PURO (testeable, sin red). Devuelve acciones:
    ('telegram',None) | ('wa_text',None) | ('wa_template','yumi_aviso').
    user_row: dict/Row con telegram_id, wa_id, wa_last_inbound_at, notify_channel.
    Regla: telegram_id negativo = placeholder WhatsApp-only (no es Telegram real).
    notify_channel: auto (default) | telegram | whatsapp | both. En 'auto', si el
    usuario está linkeado (tiene ambos) se prefiere Telegram para no duplicar.

    allow_template: si False (típico del plan FREE), NO se manda plantilla fuera de la
    ventana de 24h → el usuario free solo recibe proactividad por WhatsApp mientras la
    ventana está abierta (texto libre, gratis). El envío in-window no requiere setup de
    Meta (plantilla/verificación/pago); eso es solo para el caso fuera de ventana."""
    def _g(k):
        try:
            return user_row[k]
        except Exception:
            return None
    tg = _g("telegram_id"); wa = _g("wa_id")
    pref = (_g("notify_channel") or "auto")
    has_tg = bool(tg) and int(tg) > 0
    has_wa = bool(wa)
    want_tg = has_tg and pref in ("auto", "telegram", "both")
    want_wa = has_wa and pref in ("auto", "whatsapp", "both")
    if pref == "auto" and has_tg and has_wa:
        want_wa = False
    actions = []
    if want_tg:
        actions.append(("telegram", None))
    if want_wa:
        if wa_window_open(_g("wa_last_inbound_at"), now_utc):
            actions.append(("wa_text", None))          # dentro de ventana: gratis, siempre
        elif allow_template:
            actions.append(("wa_template", "yumi_aviso"))  # fuera de ventana: plantilla (paga) — solo si el plan lo permite
    return actions
