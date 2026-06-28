"""Generacion de un feed iCalendar (RFC 5545) suscribible en Google Calendar. Puro."""
from datetime import datetime


def ics_escape(text):
    if text is None:
        return ""
    return (str(text)
            .replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n"))


def ics_dt(iso):
    """'YYYY-MM-DDTHH:MM' o 'YYYY-MM-DD' -> 'YYYYMMDDTHHMMSS' (hora local floating)."""
    s = iso.replace(" ", "T")
    if "T" not in s:
        s += "T00:00"
    dt = datetime.fromisoformat(s)
    return dt.strftime("%Y%m%dT%H%M%S")


def fold_line(line):
    """Plegado RFC5545: lineas <=75 octetos; continuaciones con un espacio."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out = []
    chunk = b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not out else 74  # 74 deja lugar al espacio inicial
        if len(chunk) + len(b) > limit:
            out.append(chunk)
            chunk = b""
        chunk += b
    if chunk:
        out.append(chunk)
    first = out[0].decode("utf-8")
    rest = [" " + c.decode("utf-8") for c in out[1:]]
    return "\r\n".join([first] + rest)


def build_ics(events, calname="Asistente", dtstamp=None):
    """events: lista de dicts {uid, summary, start, location?, description?}.
    'start' es ISO local. Devuelve el texto .ics completo con CRLF."""
    stamp = dtstamp or datetime.now().strftime("%Y%m%dT%H%M%S")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//asistente//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(calname)}",
    ]
    for e in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ics_escape(e['uid'])}")
        lines.append(f"DTSTAMP:{stamp}")
        lines.append(f"DTSTART:{ics_dt(e['start'])}")
        lines.append(f"SUMMARY:{ics_escape(e.get('summary'))}")
        if e.get("location"):
            lines.append(f"LOCATION:{ics_escape(e['location'])}")
        if e.get("description"):
            lines.append(f"DESCRIPTION:{ics_escape(e['description'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_line(l) for l in lines) + "\r\n"
