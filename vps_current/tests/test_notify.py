import os, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import notify

NOW = datetime(2026, 7, 10, 12, 0, 0)  # "UTC" de referencia


def _ts(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")


def _row(**kw):
    base = {"telegram_id": None, "wa_id": None, "wa_last_inbound_at": None, "notify_channel": None}
    base.update(kw)
    return base


# ── ventana de 24h ──────────────────────────────────────────────
def test_window_open_recent():
    assert notify.wa_window_open(_ts(1), NOW) is True

def test_window_closed_old():
    assert notify.wa_window_open(_ts(30), NOW) is False

def test_window_edge_just_under_24h():
    assert notify.wa_window_open(_ts(23), NOW) is True

def test_window_none():
    assert notify.wa_window_open(None, NOW) is False

def test_window_garbage():
    assert notify.wa_window_open("no-es-fecha", NOW) is False


# ── router de entrega ───────────────────────────────────────────
def test_plan_telegram_only():
    assert notify.delivery_plan(_row(telegram_id=555), NOW) == [("telegram", None)]

def test_plan_wa_only_window_open():
    r = _row(wa_id="549261", telegram_id=-549261, wa_last_inbound_at=_ts(2))
    assert notify.delivery_plan(r, NOW) == [("wa_text", None)]

def test_plan_wa_only_window_closed():
    r = _row(wa_id="549261", telegram_id=-549261, wa_last_inbound_at=_ts(30))
    assert notify.delivery_plan(r, NOW) == [("wa_template", "yumi_aviso")]

def test_plan_wa_only_never_wrote():
    r = _row(wa_id="549261", telegram_id=-549261, wa_last_inbound_at=None)
    assert notify.delivery_plan(r, NOW) == [("wa_template", "yumi_aviso")]

def test_plan_linked_auto_prefers_telegram():
    # linkeado (tg real + wa) sin preferencia → solo Telegram, no duplica
    r = _row(telegram_id=555, wa_id="549261", wa_last_inbound_at=_ts(1))
    assert notify.delivery_plan(r, NOW) == [("telegram", None)]

def test_plan_linked_pref_both_open_window():
    r = _row(telegram_id=555, wa_id="549261", notify_channel="both", wa_last_inbound_at=_ts(1))
    assert notify.delivery_plan(r, NOW) == [("telegram", None), ("wa_text", None)]

def test_plan_pref_whatsapp_closed_window():
    r = _row(telegram_id=555, wa_id="549261", notify_channel="whatsapp", wa_last_inbound_at=None)
    assert notify.delivery_plan(r, NOW) == [("wa_template", "yumi_aviso")]

def test_plan_no_channels():
    assert notify.delivery_plan(_row(), NOW) == []
