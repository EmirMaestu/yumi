from datetime import date

import proactive


def test_upcoming_payments_merges_and_sorts():
    recurrings = [
        {"id": 1, "description": "Movistar", "amount": 7000.0, "currency": "ARS",
         "next_occurrence": "2026-06-25", "account_name": "MP", "user_id": 1},
        {"id": 2, "description": "Spotify", "amount": 5.0, "currency": "USD",
         "next_occurrence": "2026-07-10", "account_name": "Visa", "user_id": 1},
    ]
    cards_due = [
        {"account_id": 9, "account_name": "Naranja", "user_id": 1,
         "next_due": "2026-06-30",
         "totals": [{"currency": "ARS", "total": 120000.0}]},
    ]
    out = proactive.upcoming_payments(recurrings, cards_due, date(2026, 6, 19), horizon=30)
    # solo entra lo que cae dentro de [today, today+30] = hasta 2026-07-19
    fechas = [e["due_date"] for e in out]
    assert fechas == ["2026-06-25", "2026-06-30", "2026-07-10"]
    # tipos
    assert out[0]["kind"] == "recurring"
    assert out[1]["kind"] == "card"
    assert out[1]["label"] == "Naranja"
    # multi-moneda: el item de tarjeta conserva su lista de montos por moneda
    assert out[1]["amounts"] == [{"currency": "ARS", "total": 120000.0}]
    # recurrente: un solo monto en su moneda
    assert out[0]["amounts"] == [{"currency": "ARS", "total": 7000.0}]


def test_upcoming_payments_filters_outside_horizon():
    recurrings = [
        {"id": 1, "description": "Lejano", "amount": 1.0, "currency": "ARS",
         "next_occurrence": "2026-09-01", "account_name": "MP", "user_id": 1},
        {"id": 2, "description": "Ayer", "amount": 1.0, "currency": "ARS",
         "next_occurrence": "2026-06-18", "account_name": "MP", "user_id": 1},
    ]
    out = proactive.upcoming_payments(recurrings, [], date(2026, 6, 19), horizon=30)
    assert out == []  # uno es pasado, otro fuera de los 30 dias


def test_upcoming_payments_days_left():
    recurrings = [{"id": 1, "description": "X", "amount": 1.0, "currency": "ARS",
                   "next_occurrence": "2026-06-22", "account_name": "MP", "user_id": 1}]
    out = proactive.upcoming_payments(recurrings, [], date(2026, 6, 19), horizon=30)
    assert out[0]["days_left"] == 3


def test_upcoming_payments_today_and_boundary_included():
    # due hoy (days_left 0) y due exactamente en el limite (today+30) deben entrar
    recurrings = [
        {"id": 1, "description": "Hoy", "amount": 1.0, "currency": "ARS",
         "next_occurrence": "2026-06-19", "account_name": "MP", "user_id": 1},
        {"id": 2, "description": "Limite", "amount": 1.0, "currency": "ARS",
         "next_occurrence": "2026-07-19", "account_name": "MP", "user_id": 1},
        {"id": 3, "description": "Fuera", "amount": 1.0, "currency": "ARS",
         "next_occurrence": "2026-07-20", "account_name": "MP", "user_id": 1},
    ]
    out = proactive.upcoming_payments(recurrings, [], date(2026, 6, 19), horizon=30)
    labels = [e["label"] for e in out]
    assert labels == ["Hoy", "Limite"]
    assert out[0]["days_left"] == 0
    assert out[1]["days_left"] == 30


def test_upcoming_payments_accepts_datetime_iso():
    # next_occurrence con hora (YYYY-MM-DDTHH:MM) tambien se parsea
    recurrings = [{"id": 1, "description": "ConHora", "amount": 1.0, "currency": "ARS",
                   "next_occurrence": "2026-06-25T08:00", "account_name": "MP", "user_id": 1}]
    out = proactive.upcoming_payments(recurrings, [], date(2026, 6, 19), horizon=30)
    assert out[0]["due_date"] == "2026-06-25"
    assert out[0]["days_left"] == 6


def test_upcoming_payments_card_empty_cycle_omitted():
    # tarjeta sin ciclo cerrado (totals vacios o total 0) no aparece
    cards_due = [
        {"account_id": 9, "account_name": "Naranja", "user_id": 1,
         "next_due": "2026-06-30", "totals": []},
        {"account_id": 10, "account_name": "Visa", "user_id": 1,
         "next_due": "2026-06-30", "totals": [{"currency": "ARS", "total": 0.0}]},
    ]
    out = proactive.upcoming_payments([], cards_due, date(2026, 6, 19), horizon=30)
    assert out == []


def test_format_calendar_groups_currencies_no_cross_sum():
    items = [
        {"kind": "card", "due_date": "2026-06-30", "days_left": 11, "label": "Naranja",
         "user_id": 1, "ref_id": 9,
         "amounts": [{"currency": "ARS", "total": 120000.0},
                     {"currency": "USD", "total": 30.0}]},
        {"kind": "recurring", "due_date": "2026-06-25", "days_left": 6, "label": "Movistar",
         "user_id": 1, "ref_id": 1, "amounts": [{"currency": "ARS", "total": 7000.0}]},
    ]
    # ordenar como lo hace upcoming_payments antes de formatear
    items.sort(key=lambda e: (e["due_date"], e["kind"], e["label"]))
    txt = proactive.format_calendar(items)
    assert "Proximos pagos" in txt
    assert "Movistar" in txt and "Naranja" in txt
    # nunca suma ARS + USD: ambas monedas aparecen por separado en Naranja
    assert "120,000.00 ARS" in txt
    assert "30.00 USD" in txt
    # Movistar (25) aparece antes que Naranja (30)
    assert txt.index("Movistar") < txt.index("Naranja")


def test_format_calendar_empty():
    assert "No hay pagos" in proactive.format_calendar([])


def test_due_pushes_for_only_at_3_and_1_days():
    items = [
        {"kind": "card", "due_date": "2026-06-22", "days_left": 3, "label": "Naranja",
         "user_id": 1, "ref_id": 9, "amounts": [{"currency": "ARS", "total": 100000.0}]},
        {"kind": "recurring", "due_date": "2026-06-20", "days_left": 1, "label": "Movistar",
         "user_id": 1, "ref_id": 1, "amounts": [{"currency": "ARS", "total": 7000.0}]},
        {"kind": "recurring", "due_date": "2026-06-21", "days_left": 2, "label": "Otro",
         "user_id": 1, "ref_id": 2, "amounts": [{"currency": "ARS", "total": 1.0}]},
    ]
    pushes = proactive.due_pushes_for(items, lead_days=(3, 1))
    # solo los de 3 y 1 dias (no el de 2)
    labels = sorted(p["label"] for p in pushes)
    assert labels == ["Movistar", "Naranja"]
    naranja = [p for p in pushes if p["label"] == "Naranja"][0]
    assert "3 dias" in naranja["text"]
    assert naranja["kind"] == "card"   # se mantiene para decidir el boton
    assert naranja["user_id"] == 1
    # el de 1 dia usa "Mañana"
    movistar = [p for p in pushes if p["label"] == "Movistar"][0]
    assert "Mañana" in movistar["text"]


def test_due_pushes_for_empty_when_no_match():
    items = [
        {"kind": "recurring", "due_date": "2026-06-21", "days_left": 2, "label": "Otro",
         "user_id": 1, "ref_id": 2, "amounts": [{"currency": "ARS", "total": 1.0}]},
    ]
    assert proactive.due_pushes_for(items, lead_days=(3, 1)) == []


def test_should_run_monthly():
    assert proactive.should_run_monthly(date(2026, 7, 1)) is True
    assert proactive.should_run_monthly(date(2026, 7, 2)) is False
    assert proactive.should_run_monthly(date(2026, 1, 1)) is True


def test_last_month_range():
    assert proactive.last_month_range(date(2026, 7, 1)) == ("2026-06-01", "2026-06-30")
    assert proactive.last_month_range(date(2026, 1, 1)) == ("2025-12-01", "2025-12-31")
    assert proactive.last_month_range(date(2026, 3, 15)) == ("2026-02-01", "2026-02-28")


def test_last_month_range_leap_february():
    # 2024 es bisiesto -> febrero termina el 29
    assert proactive.last_month_range(date(2024, 3, 10)) == ("2024-02-01", "2024-02-29")


def test_fx_alert_should_fire_above():
    a = {"direction": "above", "threshold": 1500.0, "last_fired_at": None}
    assert proactive.fx_alert_should_fire(a, current_rate=1520.0) is True
    assert proactive.fx_alert_should_fire(a, current_rate=1480.0) is False


def test_fx_alert_should_fire_below():
    a = {"direction": "below", "threshold": 1000.0, "last_fired_at": None}
    assert proactive.fx_alert_should_fire(a, current_rate=950.0) is True
    assert proactive.fx_alert_should_fire(a, current_rate=1050.0) is False


def test_fx_alert_fires_exactly_at_threshold():
    above = {"direction": "above", "threshold": 1500.0, "last_fired_at": None}
    below = {"direction": "below", "threshold": 1000.0, "last_fired_at": None}
    assert proactive.fx_alert_should_fire(above, current_rate=1500.0) is True
    assert proactive.fx_alert_should_fire(below, current_rate=1000.0) is True


def test_fx_alert_none_rate_does_not_fire():
    a = {"direction": "above", "threshold": 1500.0, "last_fired_at": None}
    assert proactive.fx_alert_should_fire(a, current_rate=None) is False


def test_fx_alert_does_not_refire_same_day():
    a = {"direction": "above", "threshold": 1500.0,
         "last_fired_at": "2026-06-19T10:00"}
    # cruzo el umbral pero ya disparo hoy -> no re-dispara
    assert proactive.fx_alert_should_fire(a, current_rate=1520.0,
                                          today="2026-06-19") is False
    # otro dia, sigue cruzado -> dispara de nuevo
    assert proactive.fx_alert_should_fire(a, current_rate=1520.0,
                                          today="2026-06-20") is True
