import csv
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

from models import db


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _find_plan_with_tobogan():
    files = sorted(glob.glob("exports/merge_similares_plan_*.csv"))
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if "tobogan" in (row.get("old_nombre") or "").lower():
                        return path
        except Exception:
            continue
    return None


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


def _get_hist_qty_and_created(cur, pid):
    # Try to get last known new_qty from meta, otherwise cantidad
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
    plan_path = None
    for arg in sys.argv[1:]:
        if arg.endswith(".csv"):
            plan_path = arg
            break
    if not plan_path:
        plan_path = _find_plan_with_tobogan()
    if not plan_path:
        print("No se encontro plan con tobogan")
        return

    rows = []
    with open(plan_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if "tobogan" in (row.get("old_nombre") or "").lower():
                rows.append(row)

    if not rows:
        print("No hay filas de tobogan en el plan")
        return

    # Unique by old id
    by_id = {}
    for r in rows:
        try:
            pid = int(r.get("id") or 0)
        except Exception:
            continue
        by_id[pid] = r

    conn = db.get_connection()
    cur = conn.cursor()

    # Check which ids exist
    cur.execute("SELECT id FROM productos")
    existing_ids = {int(r[0]) for r in cur.fetchall()}

    changes = []
    inserts = 0
    updates = 0

    for pid, r in sorted(by_id.items()):
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
                "precio_venta": precio_venta,
                "precio_costo": precio_costo,
                "accion": action,
            }
        )

    if apply:
        conn.commit()
    conn.close()

    out_dir = Path("exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"restore_toboganes_{ts}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(changes[0].keys()) if changes else [])
        if changes:
            w.writeheader()
            w.writerows(changes)

    print(f"Plan usado: {plan_path}")
    print(f"Updates: {updates}  Inserts: {inserts}")
    print(f"Reporte: {out_path}")


if __name__ == "__main__":
    main()
