"""
scripts/backup_db.py

Hace una copia de seguridad del archivo SQLite DB (si aplica) en folder backups/ con timestamp.
"""
import os
import shutil
from datetime import datetime

from models import db

try:
    from cryptography.fernet import Fernet
except Exception:
    Fernet = None


def backup():
    db_path = getattr(db, "DB_PATH", None)
    if not db_path or not os.path.exists(db_path):
        print("No se encontró archivo SQLite para respaldar:", db_path)
        return
    outdir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(outdir, f"manarey_backup_{ts}.db")
    shutil.copy2(db_path, dest)

    # Si se provee MANAREY_BACKUP_KEY usamos Fernet para cifrar la copia.
    backup_key = os.environ.get("MANAREY_BACKUP_KEY")
    if backup_key and Fernet is not None:
        try:
            f = Fernet(
                backup_key.encode() if isinstance(backup_key, str) else backup_key
            )
            with open(dest, "rb") as rf:
                data = rf.read()
            enc = f.encrypt(data)
            enc_path = dest + ".enc"
            with open(enc_path, "wb") as wf:
                wf.write(enc)
            # Opcional: borrar el .db original si se desea mantener solo la versión cifrada
            print("Backup cifrado creado en", enc_path)
        except Exception as e:
            print("No se pudo cifrar backup:", e)
    else:
        if backup_key and Fernet is None:
            print(
                "MANAREY_BACKUP_KEY se ha establecido pero falta cryptography. Se creó backup sin cifrar."
            )
        print("Backup creado en", dest)


if __name__ == "__main__":
    backup()
