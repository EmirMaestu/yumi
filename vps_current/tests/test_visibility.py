import os, sys, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import visibility


def _db():
    c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
    c.executescript("""
      CREATE TABLE users(id INTEGER PRIMARY KEY, household_id INTEGER, share_all INTEGER DEFAULT 0);
      CREATE TABLE accounts(id INTEGER PRIMARY KEY, user_id INTEGER, shared INTEGER DEFAULT 0);
      CREATE TABLE eventos(id INTEGER PRIMARY KEY, user_id INTEGER, shared INTEGER DEFAULT 0);
      CREATE TABLE transactions(id INTEGER PRIMARY KEY, user_id INTEGER, account_id INTEGER);
      INSERT INTO users(id,household_id,share_all) VALUES (1,1,0),(2,1,0),(3,3,0);
      INSERT INTO accounts(id,user_id,shared) VALUES (10,1,0),(11,1,1),(12,2,0);
      INSERT INTO transactions(id,user_id,account_id) VALUES (100,1,10),(101,1,11),(102,2,12);
      INSERT INTO eventos(id,user_id,shared) VALUES (200,1,0),(201,1,1),(202,2,0);
    """)
    return c


def _members(c, uid):
    return [r[0] for r in c.execute(
        "SELECT id FROM users WHERE COALESCE(household_id,id)=(SELECT COALESCE(household_id,id) FROM users WHERE id=?)", (uid,))]


def _ids(c, table, alias, frag, params):
    return sorted(r[0] for r in c.execute(f"SELECT {alias}.id FROM {table} {alias} WHERE {frag}", params))


def test_eventos_mine_sees_all_own():
    c = _db()
    frag, p = visibility.where(asker_id=1, scope_uid=1, members=_members(c,1), alias="e", shared_expr="e.shared=1")
    assert _ids(c, "eventos", "e", frag, p) == [200, 201]


def test_eventos_ours_hides_others_private():
    c = _db()
    frag, p = visibility.where(asker_id=1, scope_uid=None, members=_members(c,1), alias="e", shared_expr="e.shared=1")
    assert _ids(c, "eventos", "e", frag, p) == [200, 201]


def test_eventos_ours_shows_others_shared():
    c = _db()
    c.execute("UPDATE eventos SET shared=1 WHERE id=202")
    frag, p = visibility.where(asker_id=1, scope_uid=None, members=_members(c,1), alias="e", shared_expr="e.shared=1")
    assert _ids(c, "eventos", "e", frag, p) == [200, 201, 202]


def test_eventos_userX_only_shared_of_X():
    c = _db()
    c.execute("UPDATE eventos SET shared=1 WHERE id=202")
    frag, p = visibility.where(asker_id=1, scope_uid=2, members=_members(c,1), alias="e", shared_expr="e.shared=1")
    assert _ids(c, "eventos", "e", frag, p) == [202]


def test_share_all_exposes_everything_of_owner():
    c = _db()
    c.execute("UPDATE users SET share_all=1 WHERE id=2")
    frag, p = visibility.where(asker_id=1, scope_uid=None, members=_members(c,1), alias="e", shared_expr="e.shared=1")
    assert _ids(c, "eventos", "e", frag, p) == [200, 201, 202]


def test_transactions_visibility_by_account():
    c = _db()
    frag, p = visibility.where(asker_id=1, scope_uid=None, members=_members(c,1), alias="t",
                               shared_expr="t.account_id IN (SELECT id FROM accounts WHERE shared=1)")
    assert _ids(c, "transactions", "t", frag, p) == [100, 101]


def test_cross_household_never():
    c = _db()
    c.execute("INSERT INTO eventos(id,user_id,shared) VALUES (300,3,1)")
    frag, p = visibility.where(asker_id=1, scope_uid=None, members=_members(c,1), alias="e", shared_expr="e.shared=1")
    assert 300 not in _ids(c, "eventos", "e", frag, p)
