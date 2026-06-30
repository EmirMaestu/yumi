"""
CRUD v2 — multi-usuario.
Cada creacion/edicion respeta el usuario logueado.
"""

import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Body, Cookie, Depends
from pydantic import BaseModel

DB_PATH = str(Path(__file__).parent / "data.db")
# # >>> shared web patch
router = APIRouter(prefix="/api")

TRASHABLE = {
    "transactions": "transactions",
    "recurring": "recurring",
    "eventos": "eventos",
    "recordatorios": "recordatorios",
    "tareas": "tareas",
    "habitos": "habito_logs",
    "notas": "notas",
}


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_crud_v2():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS trash (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity TEXT NOT NULL,
            original_id INTEGER NOT NULL,
            payload TEXT NOT NULL,
            user_id INTEGER,
            deleted_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        # defensive: ALTER si la tabla trash existia sin user_id
        cols = [r[1] for r in conn.execute("PRAGMA table_info(trash)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE trash ADD COLUMN user_id INTEGER")
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,
            source TEXT DEFAULT 'web',
            detail TEXT,
            user_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        cols = [r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE audit_log ADD COLUMN user_id INTEGER")
        conn.execute("""CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            user_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        cols = [r[1] for r in conn.execute("PRAGMA table_info(budgets)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE budgets ADD COLUMN user_id INTEGER")
        # Sustituir el UNIQUE viejo (category_id) por (category_id, user_id)
        # Solo creo el indice si no existe ya.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_budget_cat_user ON budgets(category_id, user_id)")
        conn.commit()


# ─── Auth dependency (igual que en web.py) ────────────────────────────────
SESSIONS = {}  # se podria importar de web.py, pero copia liviana funciona

def _user_for_session_local(token):
    """Cargar usuario verificando el token contra la DB (alternativa light
    para no compartir estado entre modulos)."""
    if not token: return None
    # tomamos la session del modulo web cuando esta cargado
    try:
        from web import SESSIONS as WEB_SESSIONS, _purge_sessions
        _purge_sessions()
        s = WEB_SESSIONS.get(token)
        if not s: return None
        with db() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=? AND active=1", (s["user_id"],)).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def require_user_crud(session: str = Cookie(None)):
    u = _user_for_session_local(session)
    if not u: raise HTTPException(401, "Login requerido")
    return u


def audit(conn, entity, entity_id, action, detail="", user_id=None):
    conn.execute(
        "INSERT INTO audit_log(entity, entity_id, action, detail, user_id) VALUES (?,?,?,?,?)",
        (entity, entity_id, action, str(detail)[:300], user_id),
    )


def patch_table(conn, table: str, row_id: int, fields: dict):
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        raise HTTPException(400, "Nada para actualizar")
    sets = ", ".join(f"{k}=?" for k in fields)
    cur = conn.execute(f"UPDATE {table} SET {sets} WHERE id=?", (*fields.values(), row_id))
    if cur.rowcount == 0:
        raise HTTPException(404, f"#{row_id} no existe")


def assert_ownership(conn, table, row_id, user_id, allow_shared=False, owner_col="user_id"):
    """Tira 403 si la fila no se puede tocar.
    - allow_shared=False (default): SOLO el dueño (acciones 'borrar/renombrar/editar').
    - allow_shared=True: permite COLABORAR — dueño, o ítem compartido con el hogar
      (`shared=1`), o dueño con share_all, o compartido per-member (item_shares) conmigo;
      todo acotado al MISMO HOGAR. Cubre el modelo de compartir por integrante."""
    import visibility
    if not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (row_id,)).fetchone():
        raise HTTPException(404, f"{table} #{row_id} no existe")
    ok = (visibility.can_collaborate(conn, table, row_id, user_id, owner_col=owner_col)
          if allow_shared else
          visibility.is_owner(conn, table, row_id, user_id, owner_col=owner_col))
    if not ok:
        raise HTTPException(403, f"{table} #{row_id} no es tuyo")


# ════════════════════════════════ RECURRENTES ════════════════════════════════

class RecurringIn(BaseModel):
    type: str = "gasto"
    amount: float
    currency: str = "ARS"
    account_id: int
    category_id: Optional[int] = None
    description: str
    day_of_month: int
    total_installments: Optional[int] = None
    installments_fired: Optional[int] = None


def _next_occurrence(day: int) -> str:
    today = datetime.now()
    day = max(1, min(28, day))
    candidate = today.replace(day=day, hour=8, minute=0, second=0, microsecond=0)
    if candidate.date() <= today.date():
        candidate = (candidate.replace(day=1) + timedelta(days=32)).replace(day=day)
    return candidate.strftime("%Y-%m-%d %H:%M:%S")


@router.post("/recurring")
def create_recurring(r: RecurringIn, user=Depends(require_user_crud)):
    with db() as conn:
        acc = conn.execute("SELECT user_id FROM accounts WHERE id=?", (r.account_id,)).fetchone()
        if not acc: raise HTTPException(400, "Cuenta inexistente")
        if acc["user_id"] != user["id"]: raise HTTPException(403, "Esa cuenta no es tuya")
        cur = conn.execute(
            """INSERT INTO recurring(type, amount, currency, account_id, category_id,
               description, frequency, day_of_month, next_occurrence, total_installments, installments_fired, user_id)
               VALUES (?,?,?,?,?,?,'monthly',?,?,?,?,?)""",
            (r.type, r.amount, r.currency, r.account_id, r.category_id,
             r.description, r.day_of_month, _next_occurrence(r.day_of_month),
             r.total_installments, r.installments_fired or 0, user["id"]),
        )
        audit(conn, "recurring", cur.lastrowid, "create", r.description, user["id"])
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


# ════════════════════════════════ EVENTOS ════════════════════════════════════

class EventoIn(BaseModel):
    title: str
    starts_at: str
    location: Optional[str] = None
    notes: Optional[str] = None
    reminder_offsets: Optional[list[int]] = None  # minutos antes para avisar, ej [1440, 120]


class EventoPatch(BaseModel):
    title: Optional[str] = None
    starts_at: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


@router.post("/eventos")
def create_evento(e: EventoIn, user=Depends(require_user_crud)):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO eventos(title, starts_at, location, notes, user_id) VALUES (?,?,?,?,?)",
            (e.title, e.starts_at, e.location, e.notes, user["id"]),
        )
        eid = cur.lastrowid
        # avisos linkeados al evento (recordatorios con event_id)
        if e.reminder_offsets:
            try:
                start = datetime.fromisoformat(e.starts_at.replace(" ", "T")[:16])
                ahora = datetime.now()
                for off in sorted({int(o) for o in e.reminder_offsets if int(o) > 0}, reverse=True):
                    rdt = start - timedelta(minutes=off)
                    if rdt > ahora:
                        conn.execute(
                            "INSERT INTO recordatorios(text, remind_at, source, user_id, event_id) VALUES (?,?,'web',?,?)",
                            (e.title, rdt.strftime("%Y-%m-%d %H:%M:%S"), user["id"], eid),
                        )
            except Exception:
                pass
        audit(conn, "eventos", eid, "create", e.title, user["id"])
        conn.commit()
        return {"id": eid, "ok": True}


@router.patch("/eventos/{evento_id}")
def patch_evento(evento_id: int, e: EventoPatch, user=Depends(require_user_crud)):
    with db() as conn:
        # Editar = colaborar (dueño o con quien esté compartido); borrar = solo dueño (web.py).
        assert_ownership(conn, "eventos", evento_id, user["id"], allow_shared=True)
        patch_table(conn, "eventos", evento_id, e.model_dump())
        audit(conn, "eventos", evento_id, "update", "", user["id"])
        conn.commit()
        return {"ok": True}


# ════════════════════════════════ TAREAS ═════════════════════════════════════

class TareaPatch(BaseModel):
    text: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[str] = None


@router.patch("/tareas/{tarea_id}")
def patch_tarea(tarea_id: int, t: TareaPatch, user=Depends(require_user_crud)):
    with db() as conn:
        # Editar texto/prioridad/fecha de una tarea = SOLO el dueño (colaborar = done/undone).
        assert_ownership(conn, "tareas", tarea_id, user["id"], allow_shared=False)
        patch_table(conn, "tareas", tarea_id, t.model_dump())
        audit(conn, "tareas", tarea_id, "update", "", user["id"])
        conn.commit()
        return {"ok": True}


# ═══════════════════════════════ RECORDATORIOS ═══════════════════════════════

class RecordatorioIn(BaseModel):
    text: str
    remind_at: str
    event_id: Optional[int] = None


class RecordatorioPatch(BaseModel):
    text: Optional[str] = None
    remind_at: Optional[str] = None
    event_id: Optional[int] = None  # vincular a un evento; null = desvincular


@router.post("/recordatorios")
def create_recordatorio(r: RecordatorioIn, user=Depends(require_user_crud)):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO recordatorios(text, remind_at, source, user_id, event_id) VALUES (?,?,'web',?,?)",
            (r.text, r.remind_at, user["id"], r.event_id),
        )
        audit(conn, "recordatorios", cur.lastrowid, "create", r.text, user["id"])
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


@router.patch("/recordatorios/{rec_id}")
def patch_recordatorio(rec_id: int, r: RecordatorioPatch, user=Depends(require_user_crud)):
    with db() as conn:
        # Editar/vincular = colaborar; borrar = solo dueño (web.py).
        assert_ownership(conn, "recordatorios", rec_id, user["id"], allow_shared=True)
        provided = r.model_dump(exclude_unset=True)  # distingue "no enviado" de null
        # event_id puede venir como null para DESvincular → se aplica aparte (patch_table ignora None).
        if "event_id" in provided:
            conn.execute("UPDATE recordatorios SET event_id=? WHERE id=?", (provided.pop("event_id"), rec_id))
        if provided:
            patch_table(conn, "recordatorios", rec_id, provided)
        if provided.get("remind_at"):
            conn.execute("UPDATE recordatorios SET fired=0 WHERE id=?", (rec_id,))
        audit(conn, "recordatorios", rec_id, "update", "", user["id"])
        conn.commit()
        return {"ok": True}


@router.post("/recordatorios/{rec_id}/snooze")
def snooze_recordatorio(rec_id: int, preset: str = "1h", user=Depends(require_user_crud)):
    deltas = {"1h": timedelta(hours=1), "manana": None, "semana": timedelta(days=7)}
    if preset not in deltas:
        raise HTTPException(400, "preset: 1h | manana | semana")
    if preset == "manana":
        nuevo = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0)
    else:
        nuevo = datetime.now() + deltas[preset]
    nuevo_s = nuevo.strftime("%Y-%m-%d %H:%M:%S")
    with db() as conn:
        assert_ownership(conn, "recordatorios", rec_id, user["id"], allow_shared=True)  # posponer = colaborar
        cur = conn.execute("UPDATE recordatorios SET remind_at=?, fired=0 WHERE id=?", (nuevo_s, rec_id))
        if cur.rowcount == 0:
            raise HTTPException(404, f"#{rec_id} no existe")
        audit(conn, "recordatorios", rec_id, "update", f"snooze {preset}", user["id"])
        conn.commit()
        return {"ok": True, "remind_at": nuevo_s}


# ════════════════════════════════ HÁBITOS ════════════════════════════════════

class HabitoIn(BaseModel):
    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    note: Optional[str] = None
    logged_at: Optional[str] = None


class HabitoPatch(BaseModel):
    name: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    note: Optional[str] = None
    logged_at: Optional[str] = None


@router.post("/habitos")
def create_habito(h: HabitoIn, user=Depends(require_user_crud)):
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO habito_logs(name, value, unit, note, logged_at, user_id)
               VALUES (?,?,?,?, COALESCE(?, datetime('now','localtime')), ?)""",
            (h.name, h.value, h.unit, h.note, h.logged_at, user["id"]),
        )
        audit(conn, "habitos", cur.lastrowid, "create", h.name, user["id"])
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


@router.patch("/habitos/{habito_id}")
def patch_habito(habito_id: int, h: HabitoPatch, user=Depends(require_user_crud)):
    with db() as conn:
        assert_ownership(conn, "habito_logs", habito_id, user["id"])
        patch_table(conn, "habito_logs", habito_id, h.model_dump())
        audit(conn, "habitos", habito_id, "update", "", user["id"])
        conn.commit()
        return {"ok": True}


# ════════════════════════════════ NOTAS ══════════════════════════════════════

class NotaPatch(BaseModel):
    text: Optional[str] = None
    tags: Optional[list] = None
    description: Optional[str] = None


@router.patch("/notas/{nota_id}")
def patch_nota(nota_id: int, n: NotaPatch, user=Depends(require_user_crud)):
    with db() as conn:
        assert_ownership(conn, "notas", nota_id, user["id"], allow_shared=True)
        fields = {"text": n.text,
                  "tags": json.dumps(n.tags, ensure_ascii=False) if n.tags is not None else None,
                  "description": n.description}
        patch_table(conn, "notas", nota_id, fields)
        audit(conn, "notas", nota_id, "update", "", user["id"])
        conn.commit()
        return {"ok": True}


# ═══════════════════════ PAPELERA (soft delete + deshacer) ═══════════════════

@router.post("/trash/restore/{trash_id}")
def restore(trash_id: int, user=Depends(require_user_crud)):
    with db() as conn:
        row = conn.execute("SELECT * FROM trash WHERE id=?", (trash_id,)).fetchone()
        if not row:
            raise HTTPException(404, "No está en la papelera")
        if row["user_id"] not in _hh_member_ids(conn, user["id"]):
            raise HTTPException(403, "No es tuyo")
        table = TRASHABLE[row["entity"]]
        data = json.loads(row["payload"])
        if conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (data["id"],)).fetchone():
            data.pop("id")
        cols = ", ".join(data.keys())
        marks = ", ".join("?" * len(data))
        cur = conn.execute(f"INSERT INTO {table}({cols}) VALUES ({marks})", list(data.values()))
        conn.execute("DELETE FROM trash WHERE id=?", (trash_id,))
        audit(conn, row["entity"], cur.lastrowid, "restore", "", user["id"])
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}


@router.post("/trash/{entity}/{item_id}")
def soft_delete(entity: str, item_id: int, user=Depends(require_user_crud)):
    table = TRASHABLE.get(entity)
    if not table:
        raise HTTPException(400, f"Entidad inválida. Opciones: {', '.join(TRASHABLE)}")
    with db() as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"{entity} #{item_id} no existe")
        # ownership check (propio o del hogar; NULL/otro hogar = 403)
        owner = row["user_id"] if "user_id" in row.keys() else None
        if owner not in _hh_member_ids(conn, user["id"]):
            raise HTTPException(403, f"{entity} #{item_id} no es tuyo")
        payload = json.dumps(dict(row), ensure_ascii=False)
        cur = conn.execute(
            "INSERT INTO trash(entity, original_id, payload, user_id) VALUES (?,?,?,?)",
            (entity, item_id, payload, user["id"]),
        )
        conn.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
        audit(conn, entity, item_id, "delete", "", user["id"])
        conn.commit()
        return {"ok": True, "trash_id": cur.lastrowid}


@router.get("/trash")
def list_trash(limit: int = 50, user=Depends(require_user_crud)):
    with db() as conn:
        members = _hh_member_ids(conn, user["id"]); ph = ",".join("?" for _ in members)
        rows = conn.execute(
            f"SELECT id, entity, original_id, payload, deleted_at, user_id FROM trash "
            f"WHERE user_id IN ({ph}) ORDER BY id DESC LIMIT ?",
            (*members, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload"])
            out.append(d)
        return out


@router.get("/audit")
def list_audit(limit: int = 50, user=Depends(require_user_crud)):
    with db() as conn:
        members = _hh_member_ids(conn, user["id"]); ph = ",".join("?" for _ in members)
        rows = conn.execute(
            f"SELECT * FROM audit_log WHERE user_id IN ({ph}) ORDER BY id DESC LIMIT ?",
            (*members, limit)).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════ PRESUPUESTOS ════════════════════════════════

class BudgetIn(BaseModel):
    category_id: int
    amount: float


@router.get("/budgets")
def list_budgets(user=Depends(require_user_crud)):
    mes_ini = datetime.now().strftime("%Y-%m-01")
    with db() as conn:
        rows = conn.execute(
            """SELECT b.id, b.category_id, b.amount, c.name, c.icon, c.color
               FROM budgets b JOIN categories c ON c.id=b.category_id
               WHERE b.user_id=? ORDER BY b.amount DESC""", (user["id"],)).fetchall()
        out = []
        for r in rows:
            spent = conn.execute(
                """SELECT COALESCE(SUM(amount),0) FROM transactions
                   WHERE type='gasto' AND currency='ARS' AND category_id=? AND user_id=? AND occurred_at>=?""",
                (r["category_id"], user["id"], mes_ini)).fetchone()[0]
            d = dict(r); d["spent"] = spent
            out.append(d)
        return out


@router.post("/budgets")
def upsert_budget(b: BudgetIn, user=Depends(require_user_crud)):
    if b.amount <= 0:
        raise HTTPException(400, "El monto debe ser positivo")
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM budgets WHERE category_id=? AND user_id=?",
            (b.category_id, user["id"])).fetchone()
        if existing:
            conn.execute("UPDATE budgets SET amount=? WHERE id=?", (b.amount, existing["id"]))
        else:
            conn.execute("INSERT INTO budgets(category_id, amount, user_id) VALUES (?,?,?)",
                         (b.category_id, b.amount, user["id"]))
        audit(conn, "budgets", b.category_id, "create", f"${b.amount}", user["id"])
        conn.commit()
        return {"ok": True}


@router.delete("/budgets/{bid}")
def delete_budget(bid: int, user=Depends(require_user_crud)):
    with db() as conn:
        row = conn.execute("SELECT user_id FROM budgets WHERE id=?", (bid,)).fetchone()
        if not row: raise HTTPException(404, "No existe")
        if row["user_id"] != user["id"]: raise HTTPException(403, "No es tuyo")
        conn.execute("DELETE FROM budgets WHERE id=?", (bid,)); conn.commit()
    return {"ok": True}


# ════════════════════════════════ LISTAS ════════════════════════════════
# Listas compartidas (shared=1) — espejo web de las listas del bot. Reusa
# shopping.parse_item/aisle para cantidades + gondola. Iconos inline (cosmetico).

import unicodedata
import shopping  # modulo puro en el mismo dir


def _norm_list_name(s):
    s = unicodedata.normalize("NFD", str(s or "").lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


_LIST_HINTS_WEB = [
    (("farmacia", "remedio", "medic"), "💊"),
    (("regalo", "navidad", "cumple"), "🎁"),
    (("ferreteria", "obra", "pintura"), "🔧"),
    (("verduleria", "verdura", "fruta"), "🥬"),
    (("super", "compras", "mercado", "almacen"), "🛒"),
    (("vacaciones", "viaje", "valija"), "🧳"),
    (("libreria", "utiles", "escuela", "colegio"), "✏️"),
    (("fiesta", "asado", "picada"), "🎉"),
]


def _icon_for_list(name):
    low = _norm_list_name(name)
    for kws, icon in _LIST_HINTS_WEB:
        if any(k in low for k in kws):
            return icon
    return "📝"


class ListaIn(BaseModel):
    name: str


class ItemIn(BaseModel):
    text: str


def _hh_member_ids(conn, uid):
    """IDs del hogar de uid (incl. uid). Aislamiento multi-inquilino."""
    try:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM users WHERE COALESCE(household_id,id)=(SELECT COALESCE(household_id,id) FROM users WHERE id=?)",
            (uid,)).fetchall()]
        return ids or [uid]
    except Exception:
        return [uid]


@router.get("/listas")
def get_listas(user=Depends(require_user_crud)):
    with db() as conn:
        members = _hh_member_ids(conn, user["id"])
        # Visibilidad: listas propias + las compartidas del hogar (shared / dueño con share_all).
        import visibility
        # alias="" → columnas sin prefijo (la query es `FROM lists` sin alias `t`).
        # Sin esto, visibility.where usa el alias por defecto "t" y genera
        # `t.owner_user_id` → "no such column: t.owner_user_id" → el endpoint
        # fallaba y la web mostraba "Sin listas aún" aunque hubiera listas.
        se = visibility.shared_expr_item_member("", "lists", user["id"])
        vf, vp = visibility.where(user["id"], None, members, alias="", owner_col="owner_user_id", shared_expr=se)
        lists = conn.execute(
            "SELECT id, name, icon, kind, target_date, recurrence, COALESCE(shared,0) AS shared, "
            "(SELECT COUNT(*) FROM item_shares s WHERE s.entity='lists' AND s.item_id=lists.id) AS share_count, "
            "(owner_user_id=?) AS is_owner "
            f"FROM lists WHERE COALESCE(is_template,0)=0 AND {vf} ORDER BY id", [user["id"]] + vp
        ).fetchall()
        out = []
        for l in lists:
            rows = conn.execute(
                "SELECT id, text, done, qty, unit, category FROM shopping_items "
                "WHERE list_id=? ORDER BY done ASC, COALESCE(position, id) ASC, id ASC",
                (l["id"],)).fetchall()
            items = []
            for it in rows:
                d = dict(it)
                if not d.get("category"):
                    d["category"] = shopping.aisle(d.get("text") or "")
                items.append(d)
            pend = sum(1 for it in items if not it["done"])
            out.append({**dict(l), "items": items, "pend": pend, "total": len(items)})
    return {"lists": out}


@router.post("/listas")
def create_lista(l: ListaIn, user=Depends(require_user_crud)):
    name = (l.name or "").strip()
    if not name:
        raise HTTPException(400, "Nombre requerido")
    q = _norm_list_name(name)
    import visibility
    with db() as conn:
        members = _hh_member_ids(conn, user["id"])
        ph = ",".join("?" for _ in members)
        # Dedup SOLO contra listas que el usuario puede usar (propia o compartida con él).
        # Si no, con listas privadas devolvería el id de una lista ajena que no puede ver.
        for row in conn.execute(f"SELECT id, name FROM lists WHERE COALESCE(is_template,0)=0 AND owner_user_id IN ({ph})", members).fetchall():
            if _norm_list_name(row["name"]) == q and visibility.can_collaborate(
                    conn, "lists", row["id"], user["id"], owner_col="owner_user_id"):
                return {"id": row["id"], "ok": True}
        cur = conn.execute(
            # Nace PRIVADA (shared=0): el dueño decide después compartirla (por integrante o con todo el plan).
            "INSERT INTO lists (name, kind, icon, owner_user_id, shared) VALUES (?,?,?,?,0)",
            (name.title(), "generica", _icon_for_list(name), user["id"]))
        lid = cur.lastrowid
        audit(conn, "lists", lid, "create", name, user["id"])
        conn.commit()
    return {"id": lid, "ok": True}


@router.delete("/listas/{lid}")
def delete_lista(lid: int, user=Depends(require_user_crud)):
    import visibility
    with db() as conn:
        if not conn.execute("SELECT 1 FROM lists WHERE id=?", (lid,)).fetchone():
            raise HTTPException(404, "Lista no existe")
        # Borrar la lista = SOLO el dueño (aunque esté compartida).
        if not visibility.is_owner(conn, "lists", lid, user["id"], owner_col="owner_user_id"):
            raise HTTPException(403, "Solo el dueño puede borrar la lista")
        # Limpia también las filas de compartido per-member de esta lista.
        conn.execute("DELETE FROM item_shares WHERE entity='lists' AND item_id=?", (lid,))
        conn.execute("DELETE FROM shopping_items WHERE list_id=?", (lid,))
        conn.execute("DELETE FROM lists WHERE id=?", (lid,))
        audit(conn, "lists", lid, "delete", "", user["id"])
        conn.commit()
    return {"ok": True}


@router.post("/listas/{lid}/items")
def add_list_item(lid: int, it: ItemIn, user=Depends(require_user_crud)):
    text = (it.text or "").strip()
    if not text:
        raise HTTPException(400, "Texto requerido")
    import visibility
    with db() as conn:
        if not conn.execute("SELECT 1 FROM lists WHERE id=?", (lid,)).fetchone():
            raise HTTPException(404, "Lista no existe")
        # Agregar ítems = colaborar (dueño o con quien esté compartida).
        if not visibility.can_collaborate(conn, "lists", lid, user["id"], owner_col="owner_user_id"):
            raise HTTPException(404, "Lista no existe")
        p = shopping.parse_item(text)
        cat = shopping.aisle(p["text"])
        cur = conn.execute(
            "INSERT INTO shopping_items (user_id, added_by, shared, list_id, text, qty, unit, category, done) "
            "VALUES (?,?,1,?,?,?,?,?,0)",
            (user["id"], user["id"], lid, p["text"], p["qty"], p["unit"], cat))
        iid = cur.lastrowid
        conn.commit()
    return {"id": iid, "ok": True}


@router.post("/listas/items/{iid}/toggle")
def toggle_list_item(iid: int, user=Depends(require_user_crud)):
    import visibility
    with db() as conn:
        row = conn.execute("SELECT done, list_id FROM shopping_items WHERE id=?", (iid,)).fetchone()
        if not row:
            raise HTTPException(404, "Item no existe")
        # Tildar/destildar = colaborar sobre la lista contenedora.
        if not visibility.can_collaborate(conn, "lists", row["list_id"], user["id"], owner_col="owner_user_id"):
            raise HTTPException(404, "Item no existe")
        new_done = 0 if row["done"] else 1
        conn.execute(
            "UPDATE shopping_items SET done=?, "
            "done_at=CASE WHEN ?=1 THEN datetime('now') ELSE NULL END WHERE id=?",
            (new_done, new_done, iid))
        conn.commit()
    return {"done": new_done, "ok": True}


@router.delete("/listas/items/{iid}")
def delete_list_item(iid: int, user=Depends(require_user_crud)):
    import visibility
    with db() as conn:
        row = conn.execute("SELECT list_id FROM shopping_items WHERE id=?", (iid,)).fetchone()
        if not row:
            return {"ok": True}
        # Quitar un ítem = colaborar sobre la lista contenedora.
        if not visibility.can_collaborate(conn, "lists", row["list_id"], user["id"], owner_col="owner_user_id"):
            raise HTTPException(404, "Item no existe")
        conn.execute("DELETE FROM shopping_items WHERE id=?", (iid,))
        conn.commit()
    return {"ok": True}


@router.post("/listas/{lid}/clear")
def clear_list_done(lid: int, user=Depends(require_user_crud)):
    import visibility
    with db() as conn:
        if not visibility.can_collaborate(conn, "lists", lid, user["id"], owner_col="owner_user_id"):
            raise HTTPException(404, "Lista no existe")
        cur = conn.execute("DELETE FROM shopping_items WHERE list_id=? AND done=1", (lid,))
        conn.commit()
    return {"removed": cur.rowcount, "ok": True}


@router.post("/listas/{lid}/buy-all")
def buy_all_items(lid: int, user=Depends(require_user_crud)):
    import visibility
    with db() as conn:
        if not visibility.can_collaborate(conn, "lists", lid, user["id"], owner_col="owner_user_id"):
            raise HTTPException(404, "Lista no existe")
        cur = conn.execute(
            "UPDATE shopping_items SET done=1, done_at=datetime('now') WHERE list_id=? AND done=0", (lid,))
        conn.commit()
    return {"marked": cur.rowcount, "ok": True}


# ── Plantillas (is_template=1) ──────────────────────────────────────────────

class SaveTemplateIn(BaseModel):
    name: Optional[str] = None


class UseTemplateIn(BaseModel):
    name: str
    target_list_id: Optional[int] = None


def _find_template_id(conn, name, members):
    q = _norm_list_name(name)
    ph = ",".join("?" for _ in members)
    for r in conn.execute(f"SELECT id, name FROM lists WHERE COALESCE(is_template,0)=1 AND owner_user_id IN ({ph})", members).fetchall():
        if _norm_list_name(r["name"]) == q:
            return r["id"]
    return None


@router.get("/listas/templates")
def list_templates(user=Depends(require_user_crud)):
    with db() as conn:
        members = _hh_member_ids(conn, user["id"]); ph = ",".join("?" for _ in members)
        rows = conn.execute(
            "SELECT l.id, l.name, l.icon, COUNT(s.id) AS total "
            "FROM lists l LEFT JOIN shopping_items s ON s.list_id=l.id "
            f"WHERE COALESCE(l.is_template,0)=1 AND l.owner_user_id IN ({ph}) GROUP BY l.id ORDER BY l.id", members).fetchall()
    return {"templates": [dict(r) for r in rows]}


@router.post("/listas/{lid}/save-template")
def save_as_template(lid: int, b: SaveTemplateIn, user=Depends(require_user_crud)):
    with db() as conn:
        members = _hh_member_ids(conn, user["id"]); ph = ",".join("?" for _ in members)
        src = conn.execute(f"SELECT id, name FROM lists WHERE id=? AND owner_user_id IN ({ph})", [lid] + members).fetchone()
        if not src:
            raise HTTPException(404, "Lista no existe")
        name = (b.name or src["name"] or "").strip()
        if not name:
            raise HTTPException(400, "Nombre requerido")
        items = conn.execute(
            "SELECT text, qty, unit, category, note FROM shopping_items WHERE list_id=?", (lid,)).fetchall()
        if not items:
            raise HTTPException(400, "La lista está vacía")
        tpl_id = _find_template_id(conn, name, members)
        if tpl_id:
            conn.execute("DELETE FROM shopping_items WHERE list_id=?", (tpl_id,))
        else:
            cur = conn.execute(
                "INSERT INTO lists (name, kind, icon, owner_user_id, shared, is_template) VALUES (?,?,?,?,1,1)",
                (name.title(), "generica", _icon_for_list(name), user["id"]))
            tpl_id = cur.lastrowid
        for it in items:
            conn.execute(
                "INSERT INTO shopping_items (user_id, added_by, shared, list_id, text, qty, unit, category, note, done) "
                "VALUES (?,?,1,?,?,?,?,?,?,0)",
                (user["id"], user["id"], tpl_id, it["text"], it["qty"], it["unit"], it["category"], it["note"]))
        audit(conn, "lists", tpl_id, "save_template", name, user["id"])
        conn.commit()
    return {"id": tpl_id, "count": len(items), "ok": True}


@router.post("/listas/use-template")
def instantiate_template(b: UseTemplateIn, user=Depends(require_user_crud)):
    with db() as conn:
        members = _hh_member_ids(conn, user["id"]); ph = ",".join("?" for _ in members)
        tpl_id = _find_template_id(conn, b.name, members)
        if not tpl_id:
            raise HTTPException(404, "Plantilla no existe")
        target_id = b.target_list_id
        if target_id and not conn.execute(
                f"SELECT 1 FROM lists WHERE id=? AND owner_user_id IN ({ph})", [target_id] + members).fetchone():
            raise HTTPException(404, "Lista destino no existe")
        if not target_id:
            d = (conn.execute(f"SELECT id FROM lists WHERE name='Súper' AND owner_user_id IN ({ph}) LIMIT 1", members).fetchone()
                 or conn.execute(f"SELECT id FROM lists WHERE COALESCE(is_template,0)=0 AND owner_user_id IN ({ph}) ORDER BY id LIMIT 1", members).fetchone())
            if not d:
                raise HTTPException(400, "No hay lista destino")
            target_id = d["id"]
        items = conn.execute(
            "SELECT text, qty, unit, category, note FROM shopping_items WHERE list_id=?", (tpl_id,)).fetchall()
        for it in items:
            conn.execute(
                "INSERT INTO shopping_items (user_id, added_by, shared, list_id, text, qty, unit, category, note, done) "
                "VALUES (?,?,1,?,?,?,?,?,?,0)",
                (user["id"], user["id"], target_id, it["text"], it["qty"], it["unit"], it["category"], it["note"]))
        conn.commit()
    return {"target_list_id": target_id, "count": len(items), "ok": True}
