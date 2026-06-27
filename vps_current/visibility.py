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
    o = f"{alias}.{owner_col}"
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
