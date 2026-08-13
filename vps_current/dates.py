"""Helper puro para normalizar strings de fecha/hora antes de datetime.fromisoformat.
Liviano y testeable (sin deps) — a diferencia de main.py, que no es importable en tests."""


def to_isoformat(s):
    """Devuelve `s` listo para datetime.fromisoformat.

    Solo agrega 'T00:00' si es SOLO fecha (sin hora): ni 'T' ni espacio.
    Un datetime con separador espacio ('YYYY-MM-DD HH:MM:SS') ya lo acepta
    fromisoformat → NO se toca.

    Bug histórico que tumbó el bot (crash-loop al arrancar): la versión vieja
    agregaba 'T00:00' a CUALQUIER string sin 'T', incluido 'YYYY-MM-DD HH:MM:SS'
    (separador espacio), produciendo 'YYYY-MM-DD HH:MM:SST00:00' → ValueError."""
    s = (s or "").strip()
    if "T" not in s and " " not in s:
        s += "T00:00"
    return s
