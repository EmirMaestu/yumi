"""Alertas de finanzas con dedup (card_closing/card_due/budget_warn)."""
import sqlite3
from datetime import date
import finance_alerts


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT,
            closing_day INTEGER, due_day INTEGER, active INTEGER DEFAULT 1, user_id INTEGER);
        CREATE TABLE categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
        CREATE TABLE budgets (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, amount REAL, user_id INTEGER);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, amount REAL,
            currency TEXT DEFAULT 'ARS', account_id INTEGER, category_id INTEGER, occurred_at TEXT,
            user_id INTEGER, kind TEXT DEFAULT 'normal');
        CREATE TABLE notifications_sent (id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, kind TEXT, ref TEXT, sent_at TEXT, UNIQUE(user_id, kind, ref));
    """)
    return conn


def test_mark_and_already_sent():
    conn = _db()
    assert not finance_alerts.already_sent(conn, 1, "budget_warn", "x")
    finance_alerts.mark_sent(conn, 1, "budget_warn", "x")
    assert finance_alerts.already_sent(conn, 1, "budget_warn", "x")


def test_budget_warn_at_80_and_dedup():
    conn = _db()
    conn.execute("INSERT INTO categories(id, name) VALUES (5, 'Súper')")
    conn.execute("INSERT INTO budgets(id, category_id, amount, user_id) VALUES (1, 5, 1000, 1)")
    today = date(2026, 7, 10)
    conn.execute("INSERT INTO transactions(type, amount, account_id, category_id, occurred_at, user_id, kind) "
                 "VALUES ('gasto', 850, 1, 5, '2026-07-05', 1, 'normal')")
    conn.commit()
    alerts = finance_alerts.budget_alerts(conn, 1, today)
    assert len(alerts) == 1 and alerts[0][0] == "budget_warn"
    # tras marcar, no se repite
    finance_alerts.mark_sent(conn, 1, alerts[0][0], alerts[0][1]); conn.commit()
    assert finance_alerts.budget_alerts(conn, 1, today) == []


def test_card_closing_in_3_days_and_dedup():
    conn = _db()
    conn.execute("INSERT INTO accounts(id, name, type, closing_day, due_day, active, user_id) "
                 "VALUES (1, 'Visa', 'credito', 12, 20, 1, 1)")
    conn.commit()
    today = date(2026, 7, 10)  # cierra el 12 → en 2 días
    alerts = finance_alerts.card_alerts(conn, 1, today)
    kinds = [a[0] for a in alerts]
    assert "card_closing" in kinds
    ref = next(a[1] for a in alerts if a[0] == "card_closing")
    finance_alerts.mark_sent(conn, 1, "card_closing", ref); conn.commit()
    assert not any(a[0] == "card_closing" for a in finance_alerts.card_alerts(conn, 1, today))
