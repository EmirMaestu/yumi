"""Calculo puro de proximas ocurrencias para recurrentes (pagos) y recordatorios.
Sin DB ni red: testeable offline."""
import calendar
from datetime import datetime, date, timedelta


def _as_date(current_iso):
    return datetime.fromisoformat(current_iso).date()


def _clamp_day(year, month, day):
    last = calendar.monthrange(year, month)[1]
    return min(day, last)


def next_occurrence(freq, current_iso, day_of_month):
    """Proxima fecha 'YYYY-MM-DD' para una recurrente de PAGO.
    freq: 'monthly' | 'weekly' | 'annual'.
    - monthly: mismo dia del mes siguiente (clamp a fin de mes).
    - weekly: +7 dias.
    - annual: +1 anio (clamp 29/2 -> 28/2 en anios no bisiestos).
    day_of_month solo se usa para monthly (None -> dia actual)."""
    cur = _as_date(current_iso)
    if freq == "monthly":
        ny, nm = (cur.year + 1, 1) if cur.month == 12 else (cur.year, cur.month + 1)
        d = _clamp_day(ny, nm, day_of_month or cur.day)
        return f"{ny}-{nm:02d}-{d:02d}"
    if freq == "weekly":
        nd = cur + timedelta(days=7)
        return nd.strftime("%Y-%m-%d")
    if freq == "annual":
        ny = cur.year + 1
        d = _clamp_day(ny, cur.month, cur.day)
        return f"{ny}-{cur.month:02d}-{d:02d}"
    raise ValueError(f"frecuencia no soportada: {freq}")


def next_reminder_at(recurrence_kind, current_iso):
    """Proximo 'YYYY-MM-DDTHH:MM' para un recordatorio recurrente.
    recurrence_kind: None/'' -> None (one-off). 'daily'|'weekly'|'monthly'.
    Conserva la hora; si no habia hora, asume 09:00."""
    if not recurrence_kind:
        return None
    if "T" in current_iso:
        dt = datetime.fromisoformat(current_iso.replace(" ", "T"))
    else:
        dt = datetime.fromisoformat(current_iso + "T09:00")
    if recurrence_kind == "daily":
        nd = dt + timedelta(days=1)
        return nd.strftime("%Y-%m-%dT%H:%M")
    if recurrence_kind == "weekly":
        nd = dt + timedelta(days=7)
        return nd.strftime("%Y-%m-%dT%H:%M")
    if recurrence_kind == "monthly":
        ny, nm = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
        d = _clamp_day(ny, nm, dt.day)
        return f"{ny}-{nm:02d}-{d:02d}T{dt.hour:02d}:{dt.minute:02d}"
    raise ValueError(f"recurrencia no soportada: {recurrence_kind}")
