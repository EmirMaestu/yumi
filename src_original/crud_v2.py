# ============================================================================
# CRUD V2 — completa el CRUD del dashboard + papelera con deshacer
# ============================================================================
# Archivo NUEVO: subirlo a /home/emir/asistente/crud_v2.py
#
# Integración en web.py (solo 3 líneas):
#
#   from crud_v2 import router as crud_v2_router, init_crud_v2   # arriba, con los imports
#   init_crud_v2()                                                # después de crear `app`
#   app.include_router(crud_v2_router)                            # idem
#
# Endpoints nuevos (ninguno colisiona con los existentes):
#   POST   /api/recurring                  crear recurrente desde la web
#   POST   /api/eventos                    crear evento
#   PATCH  /api/eventos/{id}               editar evento
#   PATCH  /api/tareas/{id}                editar texto/prioridad/vencimiento
#   POST   /api/recordatorios              crear recordatorio
#   PATCH  /api/recordatorios/{id}         editar / reprogramar
#   POST   /api/recordatorios/{id}/snooze  posponer (1h / mañana / semana)
#   POST   /api/habitos                    registrar hábito
#   PATCH  /api/habitos/{id}               editar registro
#   PATCH  /api/notas/{id}                 editar nota
#   POST   /api/trash/{entity}/{id}        soft delete (mueve a papelera)
#   POST   /api/trash/restore/{trash_id}   deshacer
#   GET    /api/trash?limit=50             ver papelera
#
# La papelera NO toca tus DELETE existentes: guarda la fila completa como JSON
# en una tabla `trash` y borra la original. Restaurar la re-inserta. Para
# activar el "Deshacer", apuntá los botones de borrar del frontend a
# POST /api/trash/{entity}/{id} (ver dashboard_snippets.html).
# ============================================================================

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DB_PATH = "data.db"
router = APIRouter(prefix="/api")

# entidad de la URL -> (tabla real, columnas)
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
            deleted_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,          -- create | update | delete | restore
            source TEXT DEFAULT 'web',     -- web | bot
            detail TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL UNIQUE,
            amount REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        conn.commit()


def audit(conn, entity, entity_id, action, detail=""):
    conn.execute(
        "INSERT INTO audit_log(entity, entity_id, action, detail) VALUES (?,?,?,?)",
        (entity, entity_id, action, str(detail)[:300]),
    )


def patch_table(conn, table: str, row_id: int, fields: dict):
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        raise HTTPException(400, "Nada para actualizar")
    sets = ", ".join(f"{k}=?" for k in fields)
    cur = conn.execute(f"UPDATE {table} SET {sets} WHERE id=?", (*fields.values(), row_id))
    if cur.rowcount == 0:
        raise HTTPException(404, f"#{row_id} no existe")


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


def _next_occurrence(day: int) -> str:
    today = datetime.now()
    day = max(1, min(28, day))  # 29-31 → 28 para no romper febrero
    candidate = today.replace(day=day, hour=8, minute=0, second=0, microsecond=0)
    if candidate.date() <= today.date():
        candidate = (candidate.replace(day=1) + timedelta(days=32)).replace(day=day)
    return candidate.strftime("%Y-%m-%d %H:%M:%S")


@router.post("/recurring")
def create_recurring(r: RecurringIn):
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO recurring(type, amount, currency, account_id, category_id,
               description, frequency, day_of_month, next_occurrence, total_installments)
               VALUES (?,?,?,?,?,?,'monthly',?,?,?)""",
            (r.type, r.amount, r.currency, r.account_id, r.category_id,
             r.description, r.day_of_month, _next_occurrence(r.day_of_month),
             r.total_installments),
        )
        audit(conn, "recurring", cur.lastrowid, "create", r.description)
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


# ════════════════════════════════ EVENTOS ════════════════════════════════════

class EventoIn(BaseModel):
    title: str
    starts_at: str
    location: Optional[str] = None
    notes: Optional[str] = None


class EventoPatch(BaseModel):
    title: Optional[str] = None
    starts_at: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


@router.post("/eventos")
def create_evento(e: EventoIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO eventos(title, starts_at, location, notes) VALUES (?,?,?,?)",
            (e.title, e.starts_at, e.location, e.notes),
        )
        audit(conn, "eventos", cur.lastrowid, "create", e.title)
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


@router.patch("/eventos/{evento_id}")
def patch_evento(evento_id: int, e: EventoPatch):
    with db() as conn:
        patch_table(conn, "eventos", evento_id, e.model_dump())
        audit(conn, "eventos", evento_id, "update")
        conn.commit()
        return {"ok": True}


# ════════════════════════════════ TAREAS ═════════════════════════════════════

class TareaPatch(BaseModel):
    text: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[str] = None


@router.patch("/tareas/{tarea_id}")
def patch_tarea(tarea_id: int, t: TareaPatch):
    with db() as conn:
        patch_table(conn, "tareas", tarea_id, t.model_dump())
        audit(conn, "tareas", tarea_id, "update")
        conn.commit()
        return {"ok": True}


# ═══════════════════════════════ RECORDATORIOS ═══════════════════════════════
# NOTA: los recordatorios creados acá los dispara el watchdog del bot
# (ver main_patch_watchdog.py) — sin ese patch NUNCA van a sonar.

class RecordatorioIn(BaseModel):
    text: str
    remind_at: str  # "YYYY-MM-DD HH:MM:SS" hora local


class RecordatorioPatch(BaseModel):
    text: Optional[str] = None
    remind_at: Optional[str] = None


@router.post("/recordatorios")
def create_recordatorio(r: RecordatorioIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO recordatorios(text, remind_at, source) VALUES (?,?,'web')",
            (r.text, r.remind_at),
        )
        audit(conn, "recordatorios", cur.lastrowid, "create", r.text)
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


@router.patch("/recordatorios/{rec_id}")
def patch_recordatorio(rec_id: int, r: RecordatorioPatch):
    with db() as conn:
        fields = r.model_dump()
        patch_table(conn, "recordatorios", rec_id, fields)
        if fields.get("remind_at"):  # reprogramado → vuelve a estar pendiente
            conn.execute("UPDATE recordatorios SET fired=0 WHERE id=?", (rec_id,))
        audit(conn, "recordatorios", rec_id, "update")
        conn.commit()
        return {"ok": True}


@router.post("/recordatorios/{rec_id}/snooze")
def snooze_recordatorio(rec_id: int, preset: str = "1h"):
    deltas = {"1h": timedelta(hours=1),
              "manana": None,  # mañana 09:00
              "semana": timedelta(days=7)}
    if preset not in deltas:
        raise HTTPException(400, "preset: 1h | manana | semana")
    if preset == "manana":
        nuevo = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0)
    else:
        nuevo = datetime.now() + deltas[preset]
    nuevo_s = nuevo.strftime("%Y-%m-%d %H:%M:%S")
    with db() as conn:
        cur = conn.execute(
            "UPDATE recordatorios SET remind_at=?, fired=0 WHERE id=?", (nuevo_s, rec_id))
        if cur.rowcount == 0:
            raise HTTPException(404, f"#{rec_id} no existe")
        audit(conn, "recordatorios", rec_id, "update", f"snooze {preset}")
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
def create_habito(h: HabitoIn):
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO habito_logs(name, value, unit, note, logged_at)
               VALUES (?,?,?,?, COALESCE(?, datetime('now','localtime')))""",
            (h.name, h.value, h.unit, h.note, h.logged_at),
        )
        audit(conn, "habitos", cur.lastrowid, "create", h.name)
        conn.commit()
        return {"id": cur.lastrowid, "ok": True}


@router.patch("/habitos/{habito_id}")
def patch_habito(habito_id: int, h: HabitoPatch):
    with db() as conn:
        patch_table(conn, "habito_logs", habito_id, h.model_dump())
        audit(conn, "habitos", habito_id, "update")
        conn.commit()
        return {"ok": True}


# ════════════════════════════════ NOTAS ══════════════════════════════════════

class NotaPatch(BaseModel):
    text: Optional[str] = None
    tags: Optional[list] = None


@router.patch("/notas/{nota_id}")
def patch_nota(nota_id: int, n: NotaPatch):
    with db() as conn:
        fields = {"text": n.text,
                  "tags": json.dumps(n.tags, ensure_ascii=False) if n.tags is not None else None}
        patch_table(conn, "notas", nota_id, fields)
        audit(conn, "notas", nota_id, "update")
        conn.commit()
        return {"ok": True}


# ═══════════════════════ PAPELERA (soft delete + deshacer) ═══════════════════
# OJO: restore va ANTES de soft_delete — su segmento literal "restore" debe
# matchear primero que el path genérico /trash/{entity}/{item_id}.

@router.post("/trash/restore/{trash_id}")
def restore(trash_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM trash WHERE id=?", (trash_id,)).fetchone()
        if not row:
            raise HTTPException(404, "No está en la papelera")
        table = TRASHABLE[row["entity"]]
        data = json.loads(row["payload"])
        # re-insertar con el id original si sigue libre
        if conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (data["id"],)).fetchone():
            data.pop("id")
        cols = ", ".join(data.keys())
        marks = ", ".join("?" * len(data))
        cur = conn.execute(f"INSERT INTO {table}({cols}) VALUES ({marks})", list(data.values()))
        conn.execute("DELETE FROM trash WHERE id=?", (trash_id,))
        audit(conn, row["entity"], cur.lastrowid, "restore")
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}


@router.post("/trash/{entity}/{item_id}")
def soft_delete(entity: str, item_id: int):
    table = TRASHABLE.get(entity)
    if not table:
        raise HTTPException(400, f"Entidad inválida. Opciones: {', '.join(TRASHABLE)}")
    with db() as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"{entity} #{item_id} no existe")
        payload = json.dumps(dict(row), ensure_ascii=False)
        cur = conn.execute(
            "INSERT INTO trash(entity, original_id, payload) VALUES (?,?,?)",
            (entity, item_id, payload),
        )
        conn.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
        audit(conn, entity, item_id, "delete")
        conn.commit()
        return {"ok": True, "trash_id": cur.lastrowid}


@router.get("/trash")
def list_trash(limit: int = 50):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, entity, original_id, payload, deleted_at FROM trash ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload"])
            out.append(d)
        return out


@router.get("/audit")
def list_audit(limit: int = 50):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════ PRESUPUESTOS ════════════════════════════════

class BudgetIn(BaseModel):
    category_id: int
    amount: float


@router.get("/budgets")
def list_budgets():
    mes_ini = datetime.now().strftime("%Y-%m-01")
    with db() as conn:
        rows = conn.execute(
            """SELECT b.id, b.category_id, b.amount, c.name, c.icon, c.color
               FROM budgets b JOIN categories c ON c.id=b.category_id
               ORDER BY b.amount DESC""").fetchall()
        out = []
        for r in rows:
            spent = conn.execute(
                """SELECT COALESCE(SUM(amount),0) FROM transactions
                   WHERE type='gasto' AND currency='ARS' AND category_id=? AND occurred_at>=?""",
                (r["category_id"], mes_ini)).fetchone()[0]
            d = dict(r); d["spent"] = spent
            out.append(d)
        return out


@router.post("/budgets")
def upsert_budget(b: BudgetIn):
    if b.amount <= 0:
        raise HTTPException(400, "El monto debe ser positivo")
    with db() as conn:
        conn.execute(
            """INSERT INTO budgets(category_id, amount) VALUES (?,?)
               ON CONFLICT(category_id) DO UPDATE SET amount=excluded.amount""",
            (b.category_id, b.amount))
        audit(conn, "budgets", b.category_id, "create", f"${b.amount}")
        conn.commit()
        return {"ok": True}


@router.delete("/budgets/{bid}")
def delete_budget(bid: int):
    with db() as conn:
        cur = conn.execute("DELETE FROM budgets WHERE id=?", (bid,))
        if cur.rowcount == 0:
            raise HTTPException(404, "No existe")
        conn.commit()
        return {"ok": True}
