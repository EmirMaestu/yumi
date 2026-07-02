"""Purga de la papelera de transacciones >30 días (D5)."""
import web


def test_purge_removes_old_only(api):
    with api.conn() as c:
        c.execute("INSERT INTO trash(entity, original_id, payload, user_id, deleted_at) "
                  "VALUES ('transaction', 1, '{}', 1, datetime('now','localtime','-40 days'))")
        c.execute("INSERT INTO trash(entity, original_id, payload, user_id, deleted_at) "
                  "VALUES ('transaction', 2, '{}', 1, datetime('now','localtime','-5 days'))")
        c.commit()
        web.purge_transaction_trash(c, 30)
        c.commit()
        remaining = [r["original_id"] for r in c.execute("SELECT original_id FROM trash").fetchall()]
    assert remaining == [2]
