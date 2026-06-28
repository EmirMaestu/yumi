import shopping


# ---------- parse_item ----------

def test_parse_item_qty_unit_de():
    p = shopping.parse_item("2 kg de papa")
    assert p == {"text": "papa", "qty": 2.0, "unit": "kg"}


def test_parse_item_qty_no_unit():
    p = shopping.parse_item("3 manzanas")
    assert p["qty"] == 3.0 and p["unit"] is None and p["text"] == "manzanas"


def test_parse_item_plain():
    p = shopping.parse_item("leche")
    assert p == {"text": "leche", "qty": None, "unit": None}


def test_parse_item_fraction_docena():
    p = shopping.parse_item("1/2 docena de huevos")
    assert p["qty"] == 0.5 and p["unit"] == "docena" and p["text"] == "huevos"


def test_parse_item_decimal_litros():
    p = shopping.parse_item("1,5 litros de aceite")
    assert p["qty"] == 1.5 and p["unit"] == "L" and p["text"] == "aceite"


def test_parse_item_only_qty_unit_keeps_raw():
    # sin item descriptible -> texto crudo, no rompe
    p = shopping.parse_item("2 kg")
    assert p == {"text": "2 kg", "qty": None, "unit": None}


def test_parse_item_empty():
    assert shopping.parse_item("") == {"text": "", "qty": None, "unit": None}


# ---------- aisle ----------

def test_aisle_known():
    assert shopping.aisle("leche descremada") == "Lacteos"
    assert shopping.aisle("2 kg papa") == "Verduleria"
    assert shopping.aisle("lavandina") == "Limpieza"
    assert shopping.aisle("ibuprofeno 400") == "Farmacia"


def test_aisle_unknown():
    assert shopping.aisle("cosa rara xyz") == "Otros"


# ---------- render_list ----------

def test_render_list_groups_by_aisle():
    items = [
        {"id": 1, "text": "papa", "done": 0, "qty": 2, "unit": "kg", "category": "Verduleria"},
        {"id": 2, "text": "leche", "done": 0, "category": "Lacteos"},
        {"id": 3, "text": "pan", "done": 1, "category": "Panaderia"},
    ]
    out = shopping.render_list(items, "Super", "\U0001F6D2")
    assert "Super" in out
    assert "Verduleria" in out and "Lacteos" in out
    assert "2 kg papa" in out
    # comprados en resumen al final
    assert "Comprado (1): pan" in out
    # gondolas en orden de recorrido: verduleria antes que lacteos
    assert out.index("Verduleria") < out.index("Lacteos")


def test_render_list_single_group_no_headers():
    items = [
        {"id": 1, "text": "leche", "done": 0, "category": "Lacteos"},
        {"id": 2, "text": "queso", "done": 0, "category": "Lacteos"},
    ]
    out = shopping.render_list(items)
    assert "▫️ leche" in out and "▫️ queso" in out
    # un solo grupo -> no se imprime el encabezado de gondola
    assert "Lacteos" not in out


def test_render_list_empty():
    out = shopping.render_list([], "Farmacia", "\U0001F48A")
    assert "Farmacia" in out and "vacia" in out


def test_render_list_all_done():
    items = [{"id": 1, "text": "pan", "done": 1}]
    out = shopping.render_list(items)
    assert "Todo comprado" in out


def test_render_list_subtitle():
    items = [{"id": 1, "text": "leche", "done": 0}]
    out = shopping.render_list(items, "Super", "\U0001F6D2", subtitle="📅 sáb 21 Jun · 🔁 semanal")
    assert "📅 sáb 21 Jun · 🔁 semanal" in out
    # subtitle aparece antes que los items
    assert out.index("semanal") < out.index("leche")


def test_render_list_subtitle_empty():
    out = shopping.render_list([], "Cena", "🍽️", subtitle="📅 sáb 21 Jun")
    assert "Cena" in out and "📅 sáb 21 Jun" in out and "vacia" in out


# ---------- match_item ----------

def test_match_item_exact_ci():
    items = [{"id": 1, "text": "Leche", "done": 0}, {"id": 2, "text": "pan", "done": 0}]
    assert shopping.match_item(items, "leche")["id"] == 1


def test_match_item_substring_both_ways():
    items = [{"id": 5, "text": "leche descremada", "done": 0}]
    assert shopping.match_item(items, "leche")["id"] == 5
    # query mas larga que el item tambien matchea
    items2 = [{"id": 6, "text": "leche", "done": 0}]
    assert shopping.match_item(items2, "la leche descremada")["id"] == 6


def test_match_item_prefers_pending():
    items = [{"id": 1, "text": "pan", "done": 1}, {"id": 2, "text": "pan", "done": 0}]
    assert shopping.match_item(items, "pan")["id"] == 2


def test_match_item_none():
    items = [{"id": 1, "text": "pan", "done": 0}]
    assert shopping.match_item(items, "queso") is None
