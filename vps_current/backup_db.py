"""
Backup atomico y comprimido de data.db.
Pensado para correr por cron a diario:
    0 3 * * *  cd ~/asistente && ~/asistente/venv/bin/python backup_db.py >> ~/asistente/backups/backup.log 2>&1

Usa la API de backup online de SQLite, asi que NO interrumpe al bot ni a la web
mientras escriben. Guarda los ultimos KEEP backups comprimidos en ~/asistente/backups/.
"""
import sqlite3
import gzip
import shutil
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
SRC = BASE / "data.db"
DEST_DIR = BASE / "backups"
KEEP = 14  # cantidad de backups a conservar


def main():
    DEST_DIR.mkdir(exist_ok=True)
    if not SRC.exists():
        print(f"{datetime.now():%Y-%m-%d %H:%M} ERROR: no existe {SRC}")
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp = DEST_DIR / f"data_{ts}.db"

    # Copia consistente pagina por pagina (no toma lock de escritura).
    src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    dst = sqlite3.connect(str(tmp))
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()

    # Comprimir y borrar el .db intermedio.
    gz = DEST_DIR / f"data_{ts}.db.gz"
    with open(tmp, "rb") as f_in, gzip.open(gz, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    tmp.unlink()

    # Rotacion: conservar solo los KEEP mas nuevos.
    backups = sorted(DEST_DIR.glob("data_*.db.gz"))
    for old in backups[:-KEEP]:
        old.unlink()

    kept = sorted(DEST_DIR.glob("data_*.db.gz"))
    print(f"{datetime.now():%Y-%m-%d %H:%M} OK {gz.name} ({gz.stat().st_size:,} bytes) · {len(kept)} backups en total")


if __name__ == "__main__":
    main()
