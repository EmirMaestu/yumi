"""Envío por la WhatsApp Cloud API (oficial de Meta). Compartido por web.py (respuestas
del webhook) y main.py (proactividad del watchdog), para no duplicar la lógica.

- send_text: mensaje de texto libre. SOLO válido dentro de la ventana de servicio de 24h
  (Meta rechaza texto libre fuera de ella).
- send_template: mensaje de plantilla (categoría utility). Es lo único que Meta permite
  para iniciar/reabrir conversación fuera de la ventana.

Sin dependencias externas (urllib). Fail-safe: loguea y no rompe el proceso.
Las credenciales salen del entorno (mismo .env que cargan ambos procesos)."""
import os
import json
import urllib.request

_GRAPH = "https://graph.facebook.com/v21.0"


def _cfg():
    return os.environ.get("WHATSAPP_TOKEN", ""), os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")


def _post(payload):
    token, pnid = _cfg()
    if not (token and pnid):
        return False
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{_GRAPH}/{pnid}/messages", data=data, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
        return True
    except Exception as e:
        print("whatsapp_api send fail:", e)
        return False


def send_text(to, text):
    """Texto libre (solo dentro de la ventana de 24h)."""
    if not (to and text):
        return False
    return _post({"messaging_product": "whatsapp", "to": str(to),
                  "type": "text", "text": {"body": str(text)[:4096]}})


def send_template(to, name, params=None, lang="es_AR"):
    """Plantilla de utilidad. `params` = lista de strings para las variables {{1}}, {{2}}…"""
    if not (to and name):
        return False
    params = params or []
    template = {"name": str(name), "language": {"code": lang}}
    if params:
        template["components"] = [{
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)[:1024]} for p in params],
        }]
    return _post({"messaging_product": "whatsapp", "to": str(to),
                  "type": "template", "template": template})
