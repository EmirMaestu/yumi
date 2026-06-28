"""
Extrae el HTML del dashboard desde tu web.py viejo y lo guarda en dashboard.html.
Asi el nuevo web.py lo carga desde ahi sin que tengas que copiar pegar nada.

Uso (en el VPS):
    cd ~/asistente
    python3 extract_html.py
"""

import re
import sys
from pathlib import Path

BASE = Path(__file__).parent
candidatos = []
# orden de busqueda: backups primero (mas viejo, intactos), despues web.py actual
for p in sorted(BASE.glob("web.py.bak.*"), reverse=True):
    candidatos.append(p)
candidatos.append(BASE / "web.py")

src = None
src_path = None
for p in candidatos:
    if not p.exists(): continue
    txt = p.read_text(encoding="utf-8")
    if 'HTML = r"""' in txt:
        src = txt; src_path = p; break

if not src:
    print("ERROR: no encuentro 'HTML = r\"\"\"' en ningun web.py o backup.")
    sys.exit(1)

m = re.search(r'HTML\s*=\s*r"""(.+?)"""', src, re.DOTALL)
if not m:
    print(f"ERROR: no pude matchear el bloque HTML en {src_path}")
    sys.exit(1)

html = m.group(1)
out = BASE / "dashboard.html"
out.write_text(html, encoding="utf-8")
print(f"✅ HTML extraido a {out}")
print(f"   Fuente: {src_path}")
print(f"   Tamano: {len(html):,} caracteres ({html.count(chr(10))} lineas)")
