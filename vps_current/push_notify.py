"""Envío de notificaciones push web (Web Push / VAPID).
Lo usan main.py (watchdog/avisos) y web.py (endpoints). Fail-safe: nunca rompe el flujo.

Config por env:
  VAPID_PRIVATE_KEY_PATH  ruta al PEM privado (generado con py_vapid)
  VAPID_SUBJECT           mailto:... (contacto)
  VAPID_PUBLIC_KEY        application server key (la sirve la web al navegador)
"""
import os
import json
import logging

log = logging.getLogger("push")

try:
    from pywebpush import webpush, WebPushException
    _LIB = True
except Exception:  # pragma: no cover
    _LIB = False

VAPID_PRIVATE = os.environ.get("VAPID_PRIVATE_KEY_PATH", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")
VAPID_PUBLIC = os.environ.get("VAPID_PUBLIC_KEY", "")


def enabled() -> bool:
    return bool(_LIB and VAPID_PRIVATE and os.path.exists(VAPID_PRIVATE))


def _send_one(sub, payload: dict):
    """sub: row/dict con endpoint, p256dh, auth. Devuelve (ok, reason)."""
    try:
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
            },
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE,
            vapid_claims={"sub": VAPID_SUBJECT},
            timeout=10,
        )
        return True, None
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code in (404, 410):
            return False, "expired"
        log.warning("webpush fail (%s): %s", code, e)
        return False, "error"
    except Exception as e:
        log.warning("webpush error: %s", e)
        return False, "error"


def send_to_user(conn, user_ids, title, body, url="/app/"):
    """Envía a TODAS las suscripciones de esos user_ids. Borra las expiradas.
    conn: sqlite3.Connection con row_factory=sqlite3.Row. Devuelve cuántas se enviaron."""
    if not enabled() or not user_ids:
        return 0
    ph = ",".join("?" for _ in user_ids)
    try:
        subs = conn.execute(
            f"SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id IN ({ph})",
            list(user_ids),
        ).fetchall()
    except Exception:
        return 0
    payload = {"title": title, "body": body, "url": url}
    sent = 0
    for s in subs:
        ok, reason = _send_one(s, payload)
        if ok:
            sent += 1
        elif reason == "expired":
            try:
                conn.execute("DELETE FROM push_subscriptions WHERE id=?", (s["id"],))
            except Exception:
                pass
    try:
        conn.commit()
    except Exception:
        pass
    return sent
