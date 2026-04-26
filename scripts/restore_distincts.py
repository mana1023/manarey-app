import csv
import glob
import json
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from models import db


def _now():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm(val: str) -> str:
    if val is None:
        return ""
    s = str(val).strip().lower()
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    out = []
    last_space = False
    for ch in s:
        if ch.isalnum():
            out.append(ch)
            last_space = False
        else:
            if not last_space:
                out.append(" ")
                last_space = True
    return " ".join("".join(out).split())


def _norm_compact(val: str) -> str:
    return _norm(val).replace(" ", "")


def _parse_num(val):
    try:
        return float(val)
    except Exception:
        return 0.0


def _clean_str(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s


def _plan_files():
    files = sorted(glob.glob("exports/merge_similares_plan_20260304_*.csv"))

    # order by timestamp in filename
    def _key(p):
        name = Path(p).stem
        parts = name.split("_")
        return parts[-1] if parts else name

    return sorted(files, key=_key)


def _target_names() -> set:
    names = set()

    # placard millenium 22/23/24/26
    for n in (22, 23, 24, 26):
        names.add(f"placard millenium {n}")

    # placard darkar 6/8/10/12 puertas de abrir (y dakar)
    for n in (6, 8, 10, 12):
        names.add(f"placard darkar {n} puertas de abrir")
        names.add(f"placard dakar {n} puertas de abrir")

    # cajonera 5/6/7 cajones
    for n in (5, 6, 7):
        names.add(f"cajonera {n} cajones")

    # colchon eco 13/17 alto
    for n in (13, 17):
        names.add(f"colchon eco {n}alto")
        names.add(f"colchon eco {n} alto")

    # colchon standard/estandar 13/17 alto
    for n in (13, 17):
        names.add(f"colchon standard {n}alto")
        names.add(f"colchon standard {n} alto")
        names.add(f"colchon estandar {n}alto")
        names.add(f"colchon estandar {n} alto")

    # colchon palace con/sin pillow
    names.update(
        [
            "colchon palace con pillow",
            "colchon palace sin pillow",
            "colchon palace c/pillow",
            "colchon palace s/pillow",
        ]
    )

    # colchon gold jackard/jackar con/sin pillow
    for base in ("colchon gold jackard", "colchon gold jackar"):
        names.add(f"{base} con pillow")
        names.add(f"{base} sin pillow")
        names.add(f"{base} c/pillow")
        names.add(f"{base} s/pillow")

    # escobero dos puertas 1,50 / 1,80 de alto
    for m in ("1,50", "1,80", "1.50", "1.80", "150", "180"):
        names.add(f"escobero dos puertas {m} de alto")

    # sillas
    names.update(
        [
            "silla abby doble respaldo",
            "silla aby doble respaldo",
            "silla ella",
            "silla ela",
            "silla hindu eco",
            "sillas hindu eco",
        ]
    )

    # lavarropa(s) semi automatico
    names.update(
        [
            "lavarropa semi automatico",
            "lavarropas semi automatico",
        ]
    )

    # combo taladro + amoladora/moladora
    names.update(
        [
            "combo taladro + amoladora",
            "combo taladro+amoladora",
            "combo taladro + moladora",
            "combo taladro+moladora",
        ]
    )

    # reposera(s) 5 posiciones
    names.update(
        [
            "reposera 5 posiciones",
            "reposeras 5 posiciones",
        ]
    )

    return {_norm(n) for n in names}


def _get_hist_qty_and_created(cur, pid):
    cur.execute(
        """
        SELECT cantidad, meta, created_at
        FROM historial_stock
        WHERE producto_id=%s
        ORDER BY created_at DESC
        """,
        (pid,),
    )
    rows = cur.fetchall()
    qty = None
    created_at = None
    for cantidad, meta, created_at_row in rows:
        if created_at is None and created_at_row:
            created_at = created_at_row
        if meta:
            try:
                data = json.loads(meta)
                if "new_qty" in data:
                    qty = int(data.get("new_qty") or 0)
                    break
            except Exception:
                pass
        if cantidad is not None and qty is None:
            qty = int(cantidad or 0)
    if qty is None:
        qty = 0
    return qty, created_at


def main():
    apply = "--apply" in sys.argv
    targets = _target_names()

    selected = {}
    for path in _plan_files():
        try:
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if str(row.get("is_combo")) == "1":
                        continue
                    old_name = row.get("old_nombre") or ""
                    if _norm(old_name) not in targets:
                        continue
                    try:
                        pid = int(row.get("id") or 0)
                    except Exception:
                        continue
                    if pid <= 0:
                        continue
                    if pid not in selected:
                        selected[pid] = row
        except Exception:
            continue

    if not selected:
        print("No se encontraron productos a restaurar en planes.")
        return

    conn = db.get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM productos")
    existing_ids = {int(r[0]) for r in cur.fetchall()}

    updates = 0
    inserts = 0
    changes = []

    for pid, r in selected.items():
        local = _clean_str(r.get("local")) or ""
        nombre = _clean_str(r.get("old_nombre")) or ""
        categoria = _clean_str(r.get("old_categoria")) or ""
        medida = _clean_str(r.get("old_medida")) or ""
        estado = _clean_str(r.get("old_estado")) or ""
        color = _clean_str(r.get("old_color"))
        material = _clean_str(r.get("old_material"))
        fabricante = _clean_str(r.get("old_fabricante"))
        codigo = _clean_str(r.get("old_codigo"))
        descripcion = _clean_str(r.get("old_descripcion"))
        precio_venta = _parse_num(r.get("old_precio_venta"))
        precio_costo = _parse_num(r.get("old_precio_costo"))

        qty, created_at = _get_hist_qty_and_created(cur, pid)
        updated_at = datetime.now()

        if pid in existing_ids:
            updates += 1
            if apply:
                cur.execute(
                    """
                    UPDATE productos
                    SET nombre=%s, categoria=%s, medida=%s, estado=%s, color=%s,
                        material=%s, fabricante=%s, codigo=%s, descripcion=%s,
                        precio_venta=%s, precio_costo=%s, cantidad=%s, local=%s,
                        is_combo=0, updated_at=%s
                    WHERE id=%s
                    """,
                    (
                        nombre,
                        categoria,
                        medida,
                        estado,
                        color,
                        material,
                        fabricante,
                        codigo,
                        descripcion,
                        precio_venta,
                        precio_costo,
                        qty,
                        local,
                        updated_at,
                        pid,
                    ),
                )
            action = "update"
        else:
            inserts += 1
            if apply:
                cur.execute(
                    """
                    INSERT INTO productos (
                        id, nombre, categoria, medida, estado, color, cantidad,
                        precio_costo, precio_venta, local, codigo, descripcion,
                        fabricante, material, is_combo, created_at, updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s)
                    """,
                    (
                        pid,
                        nombre,
                        categoria,
                        medida,
                        estado,
                        color,
                        qty,
                        precio_costo,
                        precio_venta,
                        local,
                        codigo,
                        descripcion,
                        fabricante,
                        material,
                        created_at or updated_at,
                        updated_at,
                    ),
                )
            action = "insert"

        changes.append(
            {
                "id": pid,
                "local": local,
                "nombre": nombre,
                "cantidad": qty,
                "accion": action,
            }
        )

    if apply:
        conn.commit()
    conn.close()

    out_dir = Path("exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"restore_distincts_{_now()}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(changes[0].keys()) if changes else [])
        if changes:
            w.writeheader()
            w.writerows(changes)

    print(f"Restaurados: {len(changes)} (updates {updates}, inserts {inserts})")
    print(f"Reporte: {out_path}")


if __name__ == "__main__":
    main()
