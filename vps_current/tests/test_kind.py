import sqlite3
import migrate_kind


def _schema(conn):
    # Esquema mínimo compatible con el real (transactions SIN kind todavía).
    conn.executescript(
        """
        CREATE TABLE categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL DEFAULT 'gasto', amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'ARS',
            account_id INTEGER NOT NULL, category_id INTEGER,
            description TEXT, occurred_at TEXT NOT NULL);
        """
    )


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _schema(conn)
    return conn


def test_apply_adds_columns_and_index():
    conn = _db()
    migrate_kind.apply(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()]
    assert "kind" in cols
    assert "transfer_group_id" in cols
    idx = [r[1] for r in conn.execute("PRAGMA index_list(transactions)").fetchall()]
    assert "idx_tx_kind" in idx


def test_default_kind_is_normal():
    conn = _db()
    migrate_kind.apply(conn)
    conn.execute("INSERT INTO transactions(amount, account_id, occurred_at) VALUES (100, 1, '2026-07-01')")
    assert conn.execute("SELECT kind FROM transactions").fetchone()["kind"] == "normal"


def test_backfill_transfer_from_category():
    conn = _db()
    conn.execute("INSERT INTO categories(id, name) VALUES (5, 'Transferencia')")
    conn.execute("INSERT INTO transactions(amount, account_id, category_id, occurred_at) VALUES (100, 1, 5, '2026-07-01')")
    migrate_kind.apply(conn)
    assert conn.execute("SELECT kind FROM transactions").fetchone()["kind"] == "transfer"


def test_backfill_adjustment_from_description():
    conn = _db()
    conn.execute("INSERT INTO transactions(amount, account_id, description, occurred_at) VALUES (500, 1, 'Ajuste de saldo', '2026-07-01')")
    migrate_kind.apply(conn)
    assert conn.execute("SELECT kind FROM transactions").fetchone()["kind"] == "adjustment"


def test_apply_is_idempotent():
    conn = _db()
    migrate_kind.apply(conn)
    migrate_kind.apply(conn)  # no debe romper ni duplicar
    cols = [r[1] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()]
    assert cols.count("kind") == 1
