"""FX correcto en overview2: EUR con tasa propia, nada ×1, unconverted (BF5/BF6/D7)."""
from datetime import datetime
import web


def _when():
    n = datetime.now()
    return f"{n.year:04d}-{n.month:02d}-10T12:00"


def test_eur_uses_own_rate_not_blue(api, monkeypatch):
    monkeypatch.setattr(web, "get_dolar_rate", lambda rt="blue": {"blue": 1000.0, "eur": 1500.0}.get(rt, 0))
    acc = api.add_account(type="dolares")
    api.add_tx(acc, 50, type="ingreso", currency="EUR", occurred_at=_when())
    ov = api.client.get("/api/overview2").json()
    assert ov["patrimonio_ars"] == 75000  # 50 × 1500 (EUR), no el blue


def test_usd_uses_blue(api, monkeypatch):
    monkeypatch.setattr(web, "get_dolar_rate", lambda rt="blue": {"blue": 1200.0}.get(rt, 0))
    acc = api.add_account(type="dolares")
    api.add_tx(acc, 10, type="ingreso", currency="USD", occurred_at=_when())
    ov = api.client.get("/api/overview2").json()
    assert ov["patrimonio_ars"] == 12000


def test_no_rate_excludes_and_marks_unconverted(api, monkeypatch):
    monkeypatch.setattr(web, "get_dolar_rate", lambda rt="blue": 0)  # blue=0, sin EUR
    acc = api.add_account(type="dolares")
    api.add_tx(acc, 100, type="ingreso", currency="USD", occurred_at=_when())
    ov = api.client.get("/api/overview2").json()
    assert ov["patrimonio_ars"] == 0  # jamás sumado 1:1
    assert any(u["currency"] == "USD" and u["amount"] == 100 for u in ov["unconverted"])
