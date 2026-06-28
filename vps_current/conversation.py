"""
Deteccion y merge de follow-ups conversacionales + fuzzy keyword recovery.
Modulo PURO: no importa entorno ni red, es testeable offline.
"""
import unicodedata
import difflib

# period words que el parser/resolve_period ya entiende (foundation main.py:1441)
_PERIOD_WORDS = {
    "hoy": "hoy", "ayer": "ayer",
    "esta semana": "semana", "la semana": "semana", "semana": "semana",
    "ultimos 7 dias": "semana", "esta semana pasada": "semana_pasada",
    "la semana pasada": "semana_pasada", "semana pasada": "semana_pasada",
    "este mes": "mes", "el mes": "mes", "mes": "mes",
    "el mes pasado": "mes_pasado", "mes pasado": "mes_pasado",
    "este ano": "ano", "el ano": "ano", "ano": "ano",
    "el ano pasado": "ano_pasado", "ano pasado": "ano_pasado",
    "todo": "todo", "historico": "todo", "siempre": "todo",
}
_SCOPE_OURS = {"los dos", "ambos", "juntos", "nosotros", "compartido", "los 2"}
_SCOPE_MINE = {"yo", "mio", "el mio", "lo mio"}


def _norm(s):
    s = unicodedata.normalize("NFD", str(s).lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.strip(" ?!.¿¡")


def is_followup(text):
    """Es una continuacion corta de una consulta previa?"""
    t = _norm(text)
    if not t:
        return False
    # demasiado larga para ser un 'y ...' -> es una consulta completa nueva
    if len(t.split()) > 7:
        return False
    if t.startswith("y "):
        return True
    if t in _PERIOD_WORDS:
        return True
    if t in _SCOPE_OURS or t in _SCOPE_MINE:
        return True
    # una sola palabra (nombre, cuenta, keyword): tratable como follow-up
    if len(t.split()) == 1:
        return True
    return False


def merge_followup(prev_consulta, text):
    """Patcha SOLO el campo que cambia en la consulta previa.
    Devuelve la nueva consulta (copia) o None si no reconocio el cambio."""
    # version normalizada para routing; raw (solo limpia) para preservar el nombre
    t = _norm(text)
    raw = str(text).strip().strip(" ?!.¿¡").strip()
    if t.startswith("y "):
        t = t[2:].strip()
        raw = raw[1:].strip() if raw[:1].lower() == "y" else raw
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (prev_consulta or {}).items()}
    filters = dict(out.get("filters") or {})
    out["filters"] = filters
    changed = False
    # periodo
    if t in _PERIOD_WORDS:
        filters["period"] = _PERIOD_WORDS[t]
        filters.pop("date_from", None); filters.pop("date_to", None)
        return out
    # scope compartido / mio
    if t in _SCOPE_OURS:
        filters["scope"] = "ours"; return out
    if t in _SCOPE_MINE:
        filters["scope"] = "mine"; return out
    # "de Lisa" / "de naranja" / bare token -> intentamos scope por nombre
    tok_norm = t
    tok_raw = raw
    if tok_norm.startswith("de "):
        tok_norm = tok_norm[3:].strip()
        tok_raw = tok_raw[3:].strip() if tok_raw.lower().startswith("de ") else tok_raw
    # solo un token simple (un nombre/keyword) cuenta como follow-up de scope.
    # frases mas largas no las reconocemos -> None (el LLM las reparsea).
    if tok_norm and len(tok_norm.split()) == 1:
        # preservamos el casing original del nombre (ej. "Lisa"); el handler valida
        name = tok_raw.split()[-1] if tok_raw.split() else tok_norm
        filters["scope"] = f"user:{name}"
        changed = True
    return out if changed else None


def fuzzy_keyword(missing_kw, candidates, cutoff=0.6):
    """Mejor match aproximado de missing_kw contra candidates (tokens/categorias).
    Devuelve el candidato original (no normalizado) o None."""
    if not missing_kw or not candidates:
        return None
    norm_map = {}
    for c in candidates:
        norm_map.setdefault(_norm(c), c)
    hits = difflib.get_close_matches(_norm(missing_kw), list(norm_map.keys()), n=1, cutoff=cutoff)
    return norm_map[hits[0]] if hits else None
