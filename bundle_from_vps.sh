#!/usr/bin/env bash
# Empaqueta el codigo actual del VPS para mandarlo a tu PC.
# Correr en el VPS:
#   bash bundle_from_vps.sh
# Despues desde tu PC (PowerShell):
#   scp emir@217.76.48.219:/tmp/asistente_bundle.tar.gz $env:USERPROFILE\Downloads\
#   tar -xzf $env:USERPROFILE\Downloads\asistente_bundle.tar.gz -C C:\Users\emirm\OneDrive\Desktop\asistant\vps_current
#
# (En Windows con tar.exe nativo: el -C necesita la carpeta destino existente.)

set -e
cd "${HOME}/asistente"

OUT="/tmp/asistente_bundle.tar.gz"

echo "Empaquetando codigo de ~/asistente ..."

# Lista de archivos vivos del proyecto
FILES=(
    main.py
    web.py
    crud_v2.py
    vencimientos.py
    dashboard.html
    .env
)

# Filtrar los que existen
EXISTING=()
for f in "${FILES[@]}"; do
    [[ -f "$f" ]] && EXISTING+=("$f")
done

# Sumar todos los .py.bak (por si quiere ver historial)
BAK_FILES=$(ls *.py.bak.* 2>/dev/null || true)

# Crear el tar
tar czf "$OUT" "${EXISTING[@]}" $BAK_FILES 2>/dev/null

echo "Bundle creado: $OUT"
echo "Tamano: $(du -h $OUT | cut -f1)"
echo ""
echo "Para descargarlo a tu PC desde PowerShell local:"
echo "  scp emir@217.76.48.219:$OUT \$env:USERPROFILE\\Downloads\\"
