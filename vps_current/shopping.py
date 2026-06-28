"""Render, parseo y matching de listas de compras. Puro (recibe dicts ya leidos de la DB)."""
import re

# Gondolas (categorias) en orden de recorrido tipico de super, con icono y keywords.
AISLES = [
    ("Verduleria", "\U0001F96C", ["papa", "papas", "tomate", "tomates", "cebolla", "lechuga",
        "zanahoria", "verdura", "verduras", "fruta", "frutas", "manzana", "banana", "naranja",
        "limon", "palta", "zapallo", "morron", "ajo", "espinaca", "rucula", "pera", "frutilla",
        "choclo", "pepino", "apio", "brocoli"]),
    ("Carniceria", "\U0001F969", ["carne", "milanesa", "milanesas", "pollo", "bife", "bifes",
        "asado", "cerdo", "chorizo", "salchicha", "salchichas", "pescado", "merluza", "peceto",
        "nalga", "molida", "jamon", "matambre", "vacio", "costilla", "pechuga"]),
    ("Lacteos", "\U0001F95B", ["leche", "yogur", "yogurt", "queso", "manteca", "crema", "ricota",
        "huevo", "huevos", "danonino", "dulce de leche", "muzzarella", "mozzarella"]),
    ("Panaderia", "\U0001F956", ["pan", "facturas", "factura", "medialunas", "tostadas", "budin",
        "galletitas", "galleta", "galletas", "bizcochos", "tapas de empanada", "prepizza"]),
    ("Almacen", "\U0001F6D2", ["arroz", "fideos", "fideo", "harina", "azucar", "sal", "aceite",
        "yerba", "mate", "polenta", "lentejas", "garbanzos", "pure", "salsa", "tomate triturado",
        "mayonesa", "ketchup", "mostaza", "cafe", "te", "mermelada", "miel", "cacao",
        "pan rallado", "caldo", "vinagre", "atun", "arvejas", "choclo en lata", "azucar"]),
    ("Bebidas", "\U0001F964", ["agua", "gaseosa", "coca", "sprite", "fanta", "cerveza", "vino",
        "jugo", "soda", "fernet", "aperitivo", "tonica", "energizante"]),
    ("Limpieza", "\U0001F9FD", ["lavandina", "detergente", "esponja", "trapo", "limpiador", "cif",
        "ayudin", "lavavajilla", "suavizante", "rollo de cocina", "papel de cocina", "bolsas",
        "bolsa de residuo", "secante", "desengrasante"]),
    ("Higiene", "\U0001F9F4", ["shampoo", "champu", "acondicionador", "jabon", "papel higienico",
        "pasta dental", "cepillo", "desodorante", "toallitas", "panales", "algodon", "afeitar",
        "hisopos", "toallas femeninas", "preservativos"]),
    ("Congelados", "\U0001F9CA", ["helado", "congelado", "congelados", "hamburguesa", "hamburguesas",
        "nuggets", "papas congeladas", "bastones", "rabas"]),
    ("Farmacia", "\U0001F48A", ["ibuprofeno", "paracetamol", "aspirina", "curita", "alcohol",
        "venda", "remedio", "pastilla", "pastillas", "ibupirac", "amoxicilina", "vitamina"]),
    ("Otros", "\U0001F4E6", []),
]
_AISLE_ICON = {name: icon for name, icon, _ in AISLES}
_AISLE_ORDER = {name: i for i, (name, _, _) in enumerate(AISLES)}

# Unidades reconocidas al parsear cantidades (alias -> forma canonica).
_UNITS = {
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg",
    "g": "g", "gr": "g", "grs": "g", "gramo": "g", "gramos": "g",
    "l": "L", "lt": "L", "lts": "L", "litro": "L", "litros": "L",
    "ml": "ml", "cc": "cc",
    "docena": "docena", "docenas": "docena",
    "paquete": "paq", "paquetes": "paq", "paq": "paq",
    "lata": "lata", "latas": "lata", "botella": "bot", "botellas": "bot",
    "unidad": "u", "unidades": "u",
}

_NUM_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?|\d+/\d+)\s+(.*)$")


def _to_num(s):
    s = s.strip()
    if "/" in s:
        a, b = s.split("/", 1)
        try:
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def parse_item(text):
    """'2 kg de papa' -> {text:'papa', qty:2.0, unit:'kg'}. '3 manzanas' -> qty 3, unit None.
    'leche' -> qty None, unit None. Si no logra separar el item, devuelve el texto crudo."""
    raw = (text or "").strip()
    if not raw:
        return {"text": "", "qty": None, "unit": None}
    m = _NUM_RE.match(raw)
    if not m:
        return {"text": raw, "qty": None, "unit": None}
    qty = _to_num(m.group(1))
    rest = m.group(2).strip()
    if qty is None or not rest:
        return {"text": raw, "qty": None, "unit": None}
    unit = None
    parts = rest.split(None, 1)
    if parts:
        cand = parts[0].lower().strip(".")
        if cand in _UNITS:
            unit = _UNITS[cand]
            rest = parts[1].strip() if len(parts) > 1 else ""
    if rest.lower().startswith("de "):
        rest = rest[3:].strip()
    if not rest:
        return {"text": raw, "qty": None, "unit": None}
    return {"text": rest, "qty": qty, "unit": unit}


def aisle(text):
    """Gondola (categoria) inferida del texto del item. 'Otros' si no matchea."""
    low = (text or "").lower()
    if not low.strip():
        return "Otros"
    for name, _icon, kws in AISLES:
        for kw in kws:
            if kw in low:
                return name
    return "Otros"


def aisle_icon(name):
    return _AISLE_ICON.get(name, "\U0001F4E6")


def _fmt_qty(it):
    """'2 kg papa' / '3 manzanas' / 'leche' segun qty/unit presentes."""
    text = it.get("text", "")
    qty = it.get("qty")
    unit = it.get("unit")
    if qty:
        q = int(qty) if float(qty).is_integer() else round(qty, 2)
        if unit:
            return f"{q} {unit} {text}"
        return f"{q} {text}"
    return text


def render_list(items, list_name=None, list_icon=None, subtitle=None):
    """items: [{id,text,done,qty?,unit?,category?}]. Pendientes agrupados por gondola; comprados al final.
    subtitle: linea opcional bajo el titulo (ej fecha objetivo / recurrencia)."""
    header_icon = list_icon or "\U0001F6D2"
    header_name = list_name or "Lista de compras"
    head = [f"{header_icon} {header_name}"]
    if subtitle:
        head.append(subtitle)
    if not items:
        return "\n".join(head) + "\n\n(vacia — agregame cosas y aparecen aca)"
    pend = [i for i in items if not i.get("done")]
    done = [i for i in items if i.get("done")]
    lines = head + [""]
    if pend:
        groups = {}
        for it in pend:
            a = it.get("category") or aisle(it.get("text", ""))
            groups.setdefault(a, []).append(it)
        multi = len(groups) > 1
        for a in sorted(groups, key=lambda n: _AISLE_ORDER.get(n, 999)):
            if multi:
                lines.append(f"{aisle_icon(a)} {a}")
            for it in groups[a]:
                prefix = "  " if multi else ""
                lines.append(f"{prefix}▫️ {_fmt_qty(it)}")
    else:
        lines.append("✅ Todo comprado!")
    if done:
        lines.append("")
        lines.append(f"✅ Comprado ({len(done)}): " + ", ".join(_fmt_qty(i) for i in done))
    return "\n".join(lines)


def match_item(items, query):
    """Busca por igualdad case-insensitive; si no, por substring. Devuelve el dict o None.
    Prioriza items pendientes (done=0) sobre comprados."""
    q = (query or "").strip().lower()
    if not q:
        return None
    ordered = [i for i in items if not i.get("done")] + [i for i in items if i.get("done")]
    for i in ordered:
        if i["text"].strip().lower() == q:
            return i
    for i in ordered:
        if q in i["text"].strip().lower() or i["text"].strip().lower() in q:
            return i
    return None
