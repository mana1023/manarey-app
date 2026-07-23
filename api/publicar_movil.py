"""Publica una version nueva de la app movil del jefe.

Sube el APK a Vercel Blob (almacenamiento persistente, el mismo de las fotos)
y registra la version en la base. La proxima vez que el jefe abra la app, le
va a ofrecer actualizarse sola.

Uso:
    python api/publicar_movil.py <ruta_apk> <version_codigo> <version_nombre> ["notas"]

Ejemplo:
    python api/publicar_movil.py C:\\...\\Manarey-Jefe.apk 2 1.0.1 "Arreglo del buscador"

version_codigo: numero entero, mas alto = mas nuevo (tiene que coincidir con
el Config.versionCodigo con el que se compilo ese APK).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

from models.db import get_connection, put_connection  # noqa: E402

BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    ruta_apk = sys.argv[1]
    version_codigo = int(sys.argv[2])
    version_nombre = sys.argv[3]
    notas = sys.argv[4] if len(sys.argv) > 4 else ""

    if not os.path.exists(ruta_apk):
        print(f"No existe el APK: {ruta_apk}")
        sys.exit(1)
    if not BLOB_TOKEN:
        print("Falta BLOB_READ_WRITE_TOKEN en el entorno.")
        sys.exit(1)

    with open(ruta_apk, "rb") as f:
        contenido = f.read()
    print(f"APK: {len(contenido) / 1_000_000:.1f} MB")

    # Subir a Vercel Blob. addRandomSuffix=1 para que cada version tenga su
    # propia URL y el celular no baje una cacheada.
    print("Subiendo a Vercel Blob...")
    ruta_blob = f"app-movil/manarey-jefe-{version_codigo}.apk"
    resp = requests.put(
        f"https://blob.vercel-storage.com/{ruta_blob}",
        data=contenido,
        headers={
            "Authorization": f"Bearer {BLOB_TOKEN}",
            "x-content-type": "application/vnd.android.package-archive",
            "x-add-random-suffix": "1",
            "x-api-version": "7",
        },
        timeout=180,
    )
    if resp.status_code >= 300:
        print(f"Fallo la subida ({resp.status_code}): {resp.text[:300]}")
        sys.exit(1)
    url = resp.json().get("url")
    print(f"Subido: {url}")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO movil_version
               (version_codigo, version_nombre, url, notas)
               VALUES (%s, %s, %s, %s)""",
            (version_codigo, version_nombre, url, notas),
        )
        conn.commit()
        print(
            f"Version {version_nombre} (codigo {version_codigo}) publicada.\n"
            "El jefe la va a ver la proxima vez que abra la app."
        )
    finally:
        put_connection(conn)


if __name__ == "__main__":
    main()
