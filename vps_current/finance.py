"""finance.py — logica financiera pura (proyeccion, presupuestos, anomalias,
metas de ahorro, deteccion de recurrentes, categorizacion aprendida).
Sin imports de entorno/DB/red: testeable offline.
"""
from __future__ import annotations
import re as _re
import statistics


def project_month_end(spent_so_far, day_of_month, days_in_month):
    """Extrapola linealmente el gasto del mes al fin de mes.
    proyeccion = spent_so_far / dias_transcurridos * dias_totales.
    day_of_month<=0 o invalido -> devuelve spent_so_far sin extrapolar.
    """
    spent_so_far = float(spent_so_far)
    if day_of_month <= 0 or days_in_month <= 0:
        return spent_so_far
    day = min(int(day_of_month), int(days_in_month))
    return spent_so_far / day * float(days_in_month)


BUDGET_WARN_PCT = 80.0


def budget_status(spent, limit):
    """Estado de un presupuesto. Devuelve {pct, level, remaining}.
    level: 'ok' (<80%), 'warn' (80-100%), 'over' (>=100%).
    limit<=0 -> level 'over', pct 0.
    """
    spent = float(spent)
    limit = float(limit)
    if limit <= 0:
        return {"pct": 0.0, "level": "over", "remaining": -spent}
    pct = round(spent / limit * 100, 1)
    if pct >= 100:
        level = "over"
    elif pct >= BUDGET_WARN_PCT:
        level = "warn"
    else:
        level = "ok"
    return {"pct": pct, "level": level, "remaining": round(limit - spent, 2)}


ANOMALY_MIN_POINTS = 4


def is_anomaly(amount, category_history):
    """True si amount es atipico vs el historico de su categoria.
    Criterio: amount > 3*median  O  amount > mean + 4*std (conservador: pocas falsas alarmas).
    Requiere >=ANOMALY_MIN_POINTS datos historicos.
    """
    hist = [float(x) for x in category_history if x is not None]
    if len(hist) < ANOMALY_MIN_POINTS:
        return False
    amount = float(amount)
    mean = statistics.fmean(hist)
    std = statistics.pstdev(hist)
    median = statistics.median(hist)
    return amount > 3 * median or amount > mean + 4 * std


def progress_bar(pct, width=10):
    """Barra de progreso con bloques llenos/vacios. pct se capa a [0,100]."""
    pct = max(0.0, min(100.0, float(pct)))
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def suggested_monthly(target, current, months_left):
    """Cuanto aportar por mes para llegar al target en months_left meses.
    months_left<=0 -> devuelve el faltante completo. Nunca negativo.
    """
    remaining = max(0.0, float(target) - float(current))
    if remaining == 0:
        return 0.0
    if months_left <= 0:
        return round(remaining, 2)
    return round(remaining / months_left, 2)


def _norm_desc(d):
    """Descripcion normalizada para agrupar/comparar: lower, strip, 30 chars."""
    return (d or "").strip().lower()[:30]


def detect_recurring(transactions, existing_keys=None):
    """Encuentra gastos que se repiten ~mensualmente y no estan ya en recurring.
    transactions: [{amount,currency,description,occurred_at}, ...]
    existing_keys: set de descripciones normalizadas ya recurrentes (se excluyen).
    Devuelve [{description, amount, currency, months, occurrences}, ...]
    ordenado por mas ocurrencias primero.
    """
    existing_keys = existing_keys or set()
    groups = {}  # (desc_norm, currency) -> list of (amount, ym, original_desc)
    for t in transactions:
        desc_norm = _norm_desc(t.get("description"))
        if not desc_norm or desc_norm in existing_keys:
            continue
        cur = t.get("currency") or "ARS"
        occ = t.get("occurred_at") or ""
        ym = occ[:7]  # YYYY-MM
        if len(ym) != 7:
            continue
        groups.setdefault((desc_norm, cur), []).append(
            (float(t.get("amount") or 0), ym, t.get("description") or desc_norm))
    out = []
    for (desc_norm, cur), items in groups.items():
        amounts = [a for a, _, _ in items]
        med = statistics.median(amounts)
        if med <= 0:
            continue
        # todos dentro de +-15% de la mediana
        if any(abs(a - med) > 0.15 * med for a in amounts):
            continue
        months = {ym for _, ym, _ in items}
        if len(months) < 2:
            continue
        out.append({
            "description": items[0][2],
            "amount": round(med, 2),
            "currency": cur,
            "months": len(months),
            "occurrences": len(items),
        })
    out.sort(key=lambda c: (-c["occurrences"], -c["months"]))
    return out


def learn_keywords(description):
    """Keywords normalizadas (>=4 chars) de una descripcion, para category_learning.
    ASCII a proposito: las keys deben ser estables, sin depender de tildes/unicode.
    """
    if not description:
        return []
    words = _re.findall(r"[a-zA-Z]+", description.lower())
    return [w for w in words if len(w) >= 4]


def pick_learned_category(learned_rows):
    """De [{category_id,count},...] devuelve el category_id con mas count, o None."""
    best = None
    for r in learned_rows:
        if best is None or r["count"] > best["count"]:
            best = r
    return best["category_id"] if best else None
