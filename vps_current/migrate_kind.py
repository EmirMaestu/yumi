"""
Agrega transactions.kind y transactions.transfer_group_id (decisión D1 del plan
de Finanzas), con índice y backfill de datos históricos.

  kind: 'normal' | 'transfer' | 'card_payment' | 'adjustment'
    - KPIs/trends solo suman kind='normal' (mata el string mágico "Transferencia"
      y saca ajustes/pagos de los agregados; BF3/C2).
  transfer_group_id: vincula las dos patas de una transferencia/pago de tarjeta.

Uso:
    cd ~/asistente
    sudo systemctl stop asistente
    cp data.db data.db.pre_kind.$(date +%Y%m%d_%H%M)
    ~/asistente/venv/bin/python migrate_kind.py
    sudo systemctl start asistente

Es idempotente.
"""

import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "data.db"

# Valores válidos de kind. transfer/card_payment solo se crean vía /api/transfers.
KINDS = ("normal", "transfer", "card_payment", "adjustment")


def apply(conn: sqlite3.Connection) -> None:
    """Agrega columnas + índice + backfill. Idempotente."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()]
    if "kind" not in cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN kind TEXT NOT NULL DEFAULT 'normal'")
    if "transfer_group_id" not in cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN transfer_group_id TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_kind ON transactions(kind)")
    backfill(conn)


def backfill(conn: sqlite3.Connection) -> None:
    """Marca datos históricos. Solo toca filas aún 'normal' (idempotente)."""
    conn.execute(
        "UPDATE transactions SET kind='transfer' "
        "WHERE kind='normal' AND category_id IN "
        "(SELECT id FROM categories WHERE name='Transferencia')"
    )
    conn.execute(
        "UPDATE transactions SET kind='adjustment' "
        "WHERE kind='normal' AND description='Ajuste de saldo'"
    )


def main():
    if not DB.exists():
        raise SystemExit(f"ERROR: no encuentro {DB}")
    conn = sqlite3.connect(DB)
    apply(conn)
    conn.commit()
    conn.close()
    print("OK. kind + transfer_group_id aplicados. Reinicia el servicio.")


if __name__ == "__main__":
    main()
