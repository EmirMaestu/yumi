import math

import finance


# --- A.2 project_month_end ---

def test_project_month_end_linear():
    # gaste 30000 en 10 dias de un mes de 30 -> proyeccion 90000
    assert finance.project_month_end(30000.0, 10, 30) == 90000.0


def test_project_month_end_last_day_no_extrapolation():
    # ultimo dia: ya esta todo, proyeccion == gastado
    assert finance.project_month_end(50000.0, 30, 30) == 50000.0


def test_project_month_end_day1():
    # dia 1, gaste 1000 -> proyeccion = 1000 * 30
    assert finance.project_month_end(1000.0, 1, 30) == 30000.0


def test_project_month_end_zero_day_guard():
    # day_of_month invalido (0) no debe dividir por cero
    assert finance.project_month_end(1000.0, 0, 30) == 1000.0


# --- A.3 budget_status ---

def test_budget_status_ok():
    s = finance.budget_status(4000.0, 10000.0)
    assert s["pct"] == 40.0
    assert s["level"] == "ok"
    assert s["remaining"] == 6000.0


def test_budget_status_warn():
    # 85% -> warn (umbral 80)
    assert finance.budget_status(8500.0, 10000.0)["level"] == "warn"


def test_budget_status_over():
    s = finance.budget_status(12000.0, 10000.0)
    assert s["level"] == "over"
    assert s["pct"] == 120.0
    assert s["remaining"] == -2000.0


def test_budget_status_zero_limit():
    s = finance.budget_status(500.0, 0.0)
    assert s["level"] == "over"
    assert s["pct"] == 0.0  # sin limite valido no calculamos pct


# --- A.4 is_anomaly ---

def test_is_anomaly_true_outlier():
    hist = [1000, 1100, 950, 1050, 1000, 980]  # ~1000
    assert finance.is_anomaly(5000, hist) is True


def test_is_anomaly_false_normal():
    hist = [1000, 1100, 950, 1050, 1000, 980]
    assert finance.is_anomaly(1200, hist) is False


def test_is_anomaly_too_few_points():
    # con <4 datos no marcamos nada
    assert finance.is_anomaly(99999, [1000, 1000, 1000]) is False


def test_is_anomaly_median_rule():
    # mean+2std no dispara pero 3x mediana si
    hist = [10, 10, 10, 10, 5000]  # mediana 10, std enorme por el 5000
    assert finance.is_anomaly(40, hist) is True  # 40 > 3*10


# --- A.5 progress_bar + suggested_monthly ---

def test_progress_bar():
    assert finance.progress_bar(0) == "░░░░░░░░░░"
    assert finance.progress_bar(50) == "█████░░░░░"
    assert finance.progress_bar(100) == "██████████"
    assert finance.progress_bar(150) == "██████████"  # cap a 100


def test_suggested_monthly_basic():
    # faltan 1500 USD, 3 meses -> 500/mes
    assert finance.suggested_monthly(2000, 500, 3) == 500.0


def test_suggested_monthly_done():
    # ya cumplida -> 0
    assert finance.suggested_monthly(2000, 2000, 5) == 0.0


def test_suggested_monthly_no_months():
    # sin meses (deadline pasado/None) -> todo lo que falta de golpe
    assert finance.suggested_monthly(2000, 500, 0) == 1500.0


# --- A.6 detect_recurring ---

def test_detect_recurring_finds_monthly():
    txs = [
        {"amount": 4990, "currency": "ARS", "description": "Netflix", "occurred_at": "2026-04-05T10:00"},
        {"amount": 4990, "currency": "ARS", "description": "Netflix", "occurred_at": "2026-05-05T10:00"},
        {"amount": 5290, "currency": "ARS", "description": "netflix",  "occurred_at": "2026-06-05T10:00"},
        {"amount": 1200, "currency": "ARS", "description": "Cafe",     "occurred_at": "2026-06-01T09:00"},
    ]
    out = finance.detect_recurring(txs, existing_keys=set())
    assert len(out) == 1
    c = out[0]
    assert c["description"] == "Netflix"  # primera grafia vista
    assert c["currency"] == "ARS"
    assert c["months"] == 3
    assert c["occurrences"] == 3


def test_detect_recurring_excludes_existing():
    txs = [
        {"amount": 4990, "currency": "ARS", "description": "Netflix", "occurred_at": "2026-04-05T10:00"},
        {"amount": 4990, "currency": "ARS", "description": "Netflix", "occurred_at": "2026-05-05T10:00"},
    ]
    out = finance.detect_recurring(txs, existing_keys={"netflix"})
    assert out == []


def test_detect_recurring_needs_two_months():
    txs = [
        {"amount": 4990, "currency": "ARS", "description": "Netflix", "occurred_at": "2026-05-05T10:00"},
        {"amount": 4990, "currency": "ARS", "description": "Netflix", "occurred_at": "2026-05-20T10:00"},
    ]
    # mismo mes -> no es recurrente
    assert finance.detect_recurring(txs, existing_keys=set()) == []


def test_detect_recurring_amount_dispersion_excluded():
    txs = [
        {"amount": 1000, "currency": "ARS", "description": "Varios", "occurred_at": "2026-04-05T10:00"},
        {"amount": 9000, "currency": "ARS", "description": "Varios", "occurred_at": "2026-05-05T10:00"},
    ]
    # montos muy dispares -> no candidato
    assert finance.detect_recurring(txs, existing_keys=set()) == []


# --- A.7 learn_keywords + pick_learned_category ---

def test_learn_keywords():
    assert finance.learn_keywords("Cafe en Starbucks") == ["cafe", "starbucks"]
    assert finance.learn_keywords("Uber") == ["uber"]
    assert finance.learn_keywords("a la b") == []  # nada >=4 chars
    assert finance.learn_keywords("Pago YPF nafta") == ["pago", "nafta"]  # ypf=3 chars excluido


def test_pick_learned_category():
    rows = [{"category_id": 5, "count": 2}, {"category_id": 9, "count": 7}]
    assert finance.pick_learned_category(rows) == 9
    assert finance.pick_learned_category([]) is None
