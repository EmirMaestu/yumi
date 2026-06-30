"""Regla central de visibilidad (privacidad por hogar). Devuelve fragmento SQL + params.
Lo usan main.py (bot), web.py y crud_v2.py para no duplicar la regla.

Modelo: ves un item si es tuyo, o si su dueno (de tu hogar) tiene share_all=1, o si el
item esta compartido (shared). En finanzas, `shared` del item = la cuenta (account.shared).
"""

def where(asker_id, scope_uid, members, alias="t", owner_col="user_id", shared_expr=None):
    """Devuelve (sql_fragment, params) para filtrar filas visibles segun el scope.
      scope_uid == asker_id  -> 'mine' (todo lo propio)
      scope_uid is None      -> 'ours' (propio + compartido del hogar)
      scope_uid == X (!=asker)-> 'user:X' (solo lo compartido de X)
    `shared_expr`: SQL booleano que indica que la fila esta compartida (sin params). Para
    items: f"{alias}.shared=1". Para transacciones: subquery de cuentas compartidas.
    """
    o = f"{alias}.{owner_col}" if alias else owner_col
    sa = f"{o} IN (SELECT id FROM users WHERE share_all=1)"
    shared = f"({shared_expr} OR {sa})" if shared_expr else f"({sa})"
    if scope_uid is not None and scope_uid == asker_id:
        return f"{o} = ?", [asker_id]
    if scope_uid is not None:  # user:X, X != asker -> solo lo compartido de X
        return f"({o} = ? AND {shared})", [scope_uid]
    # ours: dentro del hogar, lo propio o lo compartido
    ph = ",".join("?" for _ in members) or "NULL"
    return f"({o} IN ({ph}) AND ({o} = ? OR {shared}))", [*members, asker_id]


def shared_expr_item(alias):
    """`shared_expr` para entidades con columna `shared` (eventos/tareas/notas/recordatorios/lists)."""
    return f"{alias}.shared=1"


def shared_expr_tx(alias):
    """`shared_expr` para transacciones: visibilidad por la cuenta (account.shared)."""
    return f"{alias}.account_id IN (SELECT id FROM accounts WHERE shared=1)"


def shared_expr_item_member(alias, entity, asker_id):
    """`shared_expr` para tareas/notas/lists con compartir POR INTEGRANTE:
    la fila es visible si está compartida con todo el hogar (`shared=1`) O si está
    compartida puntualmente conmigo (fila en item_shares). `visibility.where` ya
    agrega el caso share_all del dueño y acota al hogar.

    Sin params (se embeben valores): `entity` es un literal interno (se sanitiza igual)
    y `asker_id` se castea a int → no hay inyección."""
    a = f"{alias}." if alias else ""
    ent = str(entity).replace("'", "")
    aid = int(asker_id)
    return (f"({a}shared=1 OR EXISTS (SELECT 1 FROM item_shares s "
            f"WHERE s.entity='{ent}' AND s.item_id={a}id AND s.shared_with_user_id={aid}))")


# ─────────────────────── Permisos de escritura (per-member) ───────────────────────
# Helpers que SÍ consultan la DB (a diferencia de los de arriba, que solo arman SQL).
# Acceso por índice (row[0], row[1]) para funcionar con o sin row_factory=Row.

def _hh_members(conn, user_id):
    """IDs del hogar de user_id (incluye al propio). Aislamiento multi-inquilino."""
    try:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM users WHERE COALESCE(household_id,id)="
            "(SELECT COALESCE(household_id,id) FROM users WHERE id=?)", (user_id,)).fetchall()]
        return ids or [user_id]
    except Exception:
        return [user_id]


def _safe_ent(entity):
    return str(entity).replace('"', '').replace("'", "")


def is_owner(conn, entity, item_id, user_id, owner_col="user_id"):
    """True solo si user_id es el DUEÑO del ítem (acciones 'solo dueño': borrar/renombrar)."""
    ent = _safe_ent(entity); col = _safe_ent(owner_col)
    row = conn.execute(f'SELECT "{col}" FROM "{ent}" WHERE id=?', (item_id,)).fetchone()
    if not row:
        return False
    owner = row[0]
    return owner is not None and owner == user_id


def can_collaborate(conn, entity, item_id, user_id, owner_col="user_id"):
    """True si user_id puede COLABORAR sobre el ítem: es el dueño, O (mismo hogar Y
    (compartido con todo el hogar `shared=1`, O dueño con share_all, O fila en
    item_shares para él)). Cubre tareas/notas/lists. NUNCA cruza hogares."""
    ent = _safe_ent(entity); col = _safe_ent(owner_col)
    row = conn.execute(f'SELECT "{col}", COALESCE(shared,0) FROM "{ent}" WHERE id=?',
                       (item_id,)).fetchone()
    if not row:
        return False
    owner, sh = row[0], row[1]
    if owner is not None and owner == user_id:
        return True
    if owner not in _hh_members(conn, user_id):
        return False  # distinto hogar → jamás
    if sh:
        return True  # compartido con todo el hogar
    if conn.execute("SELECT 1 FROM users WHERE id=? AND share_all=1", (owner,)).fetchone():
        return True
    if conn.execute("SELECT 1 FROM item_shares WHERE entity=? AND item_id=? AND shared_with_user_id=?",
                    (ent, item_id, user_id)).fetchone():
        return True
    return False
