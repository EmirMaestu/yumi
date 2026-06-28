"""Rachas (streaks) y progreso semanal de habitos + sparkline unicode. Puro."""
from datetime import date, datetime, timedelta


def _to_date(s):
    s = str(s).strip().replace("T", " ")
    return datetime.fromisoformat(s.split(" ")[0]).date()


def current_streak(date_strs, today):
    """Dias consecutivos hasta hoy (o hasta ayer si hoy aun no hay log).
    date_strs: iterable de 'YYYY-MM-DD' (o con hora). today: datetime.date.
    Devuelve int (0 si la racha esta cortada)."""
    days = {_to_date(s) for s in date_strs}
    if not days:
        return 0
    # ancla: hoy si hizo hoy; si no, ayer (la racha sigue viva hasta ayer)
    if today in days:
        anchor = today
    elif (today - timedelta(days=1)) in days:
        anchor = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    d = anchor
    while d in days:
        streak += 1
        d -= timedelta(days=1)
    return streak


def weekly_progress(count_this_week, goal_per_week):
    """(count, goal, pct) donde pct es 0..100 redondeado, o None si no hay meta."""
    if not goal_per_week:
        return (count_this_week, goal_per_week, None)
    pct = min(100, round(count_this_week * 100 / goal_per_week))
    return (count_this_week, goal_per_week, pct)


def sparkline(day_flags):
    """7 cajitas (lunes->domingo). True=hecho (verde), False=no (gris).
    Rellena a 7 por la izquierda con grises si faltan."""
    flags = list(day_flags)[-7:]
    flags = [False] * (7 - len(flags)) + flags
    return "".join("\U0001F7E9" if f else "⬜" for f in flags)
