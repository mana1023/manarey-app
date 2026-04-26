import csv
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from models import db


def _now():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _norm_text(val):
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


def _norm_medida(val):
    if val is None:
        return ""
    s = str(val).strip().lower()
    if not s or s in ("-", "â€”"):
        return ""
    s = s.replace(" ", "")
    s = s.replace(",", "")
    s = s.replace(".", "")
    s = s.replace("-", "")
    if "plaza" in s:
        s = s.replace("plazas", "plaza")
        num = s.replace("plaza", "")
        return (num + "plaza") if num else "plaza"
    return s


@dataclass
class Item:
    producto_id: int
    cantidad: int
    nombre: str
    categoria: str
    medida: str
    estado: str
    color: str
    fabricante: str

    n_nombre: str
    n_categoria: str
    n_medida: str


@dataclass
class Combo:
    id: int
    nombre: str
    categoria: str
    medida: str
    local: str
    descripcion: str
    precio_venta: float
    precio_costo: float


def _is_colchon_text(txt: str) -> bool:
    n = _norm_text(txt)
    return "colchon" in n


def _is_box_text(txt: str) -> bool:
    n = _norm_text(txt)
    return "box" in n


def _build_item(row, prod_map) -> Item:
    pid = int(row.get("producto_id") or 0)
    prod = prod_map.get(pid) or {}

    nombre = (row.get("producto_nombre") or prod.get("nombre") or "").strip()
    categoria = (row.get("producto_categoria") or prod.get("categoria") or "").strip()
    medida = (row.get("producto_medida") or prod.get("medida") or "").strip()
    estado = (row.get("producto_estado") or prod.get("estado") or "").strip()
    color = (row.get("producto_color") or prod.get("color") or "").strip()
    fabricante = (
        row.get("producto_fabricante") or prod.get("fabricante") or ""
    ).strip()

    return Item(
        producto_id=pid,
        cantidad=int(row.get("cantidad") or 0),
        nombre=nombre,
        categoria=categoria,
        medida=medida,
        estado=estado,
        color=color,
        fabricante=fabricante,
        n_nombre=_norm_text(nombre),
        n_categoria=_norm_text(categoria),
        n_medida=_norm_medida(medida),
    )


def _choose_pair(
    colchon_items: List[Item],
    box_items: List[Item],
    combo_med_norm: str,
) -> Optional[Tuple[Item, Item]]:
    pairs = []
    for c in colchon_items:
        for b in box_items:
            cm = c.n_medida or combo_med_norm
            bm = b.n_medida or combo_med_norm
            if combo_med_norm:
                if cm and cm != combo_med_norm:
                    continue
                if bm and bm != combo_med_norm:
                    continue
            if cm and bm and cm != bm:
                continue
            score = 0
            if cm and bm and cm == bm:
                score += 2
            if combo_med_norm and cm == combo_med_norm and bm == combo_med_norm:
                score += 1
            # prefer items with explicit medida
            if c.n_medida:
                score += 0.5
            if b.n_medida:
                score += 0.5
            pairs.append((score, c, b))
    if not pairs:
        return None
    pairs.sort(key=lambda x: x[0], reverse=True)
    return pairs[0][1], pairs[0][2]


def _find_product_candidate(prod_list, local, kind, med_norm):
    # kind: 'colchon' or 'box'
    matches = []
    for p in prod_list:
        if p.get("local") != local:
            continue
        if int(p.get("is_combo") or 0) == 1:
            continue
        name = p.get("nombre") or ""
        cat = p.get("categoria") or ""
        if kind == "colchon" and not (_is_colchon_text(name) or _is_colchon_text(cat)):
            continue
        if kind == "box" and not (_is_box_text(name) or _is_box_text(cat)):
            continue
        pmed = _norm_medida(p.get("medida"))
        if med_norm and pmed and pmed != med_norm:
            continue
        matches.append(p)
    if len(matches) == 1:
        return matches[0]
    return None


def main():
    apply = "--apply" in sys.argv

    conn = db.get_connection()
    cur = conn.cursor()
    ph = "%s" if db.is_postgres() else "?"

    # productos base
    cur.execute(
        """
        SELECT id, nombre, categoria, medida, estado, color, fabricante, local, is_combo
        FROM productos
        """
    )
    prod_rows = cur.fetchall()
    prod_cols = [
        "id",
        "nombre",
        "categoria",
        "medida",
        "estado",
        "color",
        "fabricante",
        "local",
        "is_combo",
    ]
    products = [dict(zip(prod_cols, r)) for r in prod_rows]
    prod_map = {int(p["id"]): p for p in products}

    # combos
    cur.execute(
        """
        SELECT id, nombre, categoria, medida, local, descripcion, precio_venta, precio_costo
        FROM productos
        WHERE COALESCE(is_combo,0)=1
        """
    )
    combo_rows = cur.fetchall()
    combos = [
        Combo(
            id=int(r[0]),
            nombre=r[1] or "",
            categoria=r[2] or "",
            medida=r[3] or "",
            local=r[4] or "",
            descripcion=r[5] or "",
            precio_venta=float(r[6] or 0),
            precio_costo=float(r[7] or 0),
        )
        for r in combo_rows
    ]

    # combo items
    cur.execute(
        """
        SELECT combo_producto_id, producto_id, cantidad,
               producto_nombre, producto_categoria, producto_medida,
               producto_estado, producto_color, producto_fabricante
        FROM combo_items
        """
    )
    items_by_combo = {}
    for row in cur.fetchall():
        combo_id = int(row[0] or 0)
        items_by_combo.setdefault(combo_id, []).append(
            {
                "producto_id": row[1],
                "cantidad": row[2],
                "producto_nombre": row[3],
                "producto_categoria": row[4],
                "producto_medida": row[5],
                "producto_estado": row[6],
                "producto_color": row[7],
                "producto_fabricante": row[8],
            }
        )

    fixes = []
    reviews = []

    for combo in combos:
        combo_items = items_by_combo.get(combo.id, [])
        if not combo_items:
            continue

        # detectar combos de colchon
        is_colchon_combo = (
            _is_colchon_text(combo.nombre)
            or _is_colchon_text(combo.descripcion)
            or _is_colchon_text(combo.categoria)
        )
        for it in combo_items:
            if _is_colchon_text(it.get("producto_nombre") or "") or _is_colchon_text(
                it.get("producto_categoria") or ""
            ):
                is_colchon_combo = True
                break
        if not is_colchon_combo:
            continue

        built_items = [_build_item(it, prod_map) for it in combo_items]
        colchon_items = [
            it
            for it in built_items
            if _is_colchon_text(it.nombre) or _is_colchon_text(it.categoria)
        ]
        box_items = [
            it
            for it in built_items
            if _is_box_text(it.nombre) or _is_box_text(it.categoria)
        ]

        combo_med_norm = _norm_medida(combo.medida)
        pair = _choose_pair(colchon_items, box_items, combo_med_norm)

        # fallback: buscar productos por local/medida
        fallback_used = False
        if pair is None:
            colchon_p = _find_product_candidate(
                products, combo.local, "colchon", combo_med_norm
            )
            box_p = _find_product_candidate(
                products, combo.local, "box", combo_med_norm
            )
            if colchon_p and box_p:
                # crear items con datos de producto
                c_item = Item(
                    producto_id=int(colchon_p["id"]),
                    cantidad=1,
                    nombre=colchon_p.get("nombre") or "",
                    categoria=colchon_p.get("categoria") or "",
                    medida=colchon_p.get("medida") or "",
                    estado=colchon_p.get("estado") or "",
                    color=colchon_p.get("color") or "",
                    fabricante=colchon_p.get("fabricante") or "",
                    n_nombre=_norm_text(colchon_p.get("nombre")),
                    n_categoria=_norm_text(colchon_p.get("categoria")),
                    n_medida=_norm_medida(colchon_p.get("medida")),
                )
                b_item = Item(
                    producto_id=int(box_p["id"]),
                    cantidad=1,
                    nombre=box_p.get("nombre") or "",
                    categoria=box_p.get("categoria") or "",
                    medida=box_p.get("medida") or "",
                    estado=box_p.get("estado") or "",
                    color=box_p.get("color") or "",
                    fabricante=box_p.get("fabricante") or "",
                    n_nombre=_norm_text(box_p.get("nombre")),
                    n_categoria=_norm_text(box_p.get("categoria")),
                    n_medida=_norm_medida(box_p.get("medida")),
                )
                pair = (c_item, b_item)
                fallback_used = True

        if pair is None:
            reviews.append(
                {
                    "combo_id": combo.id,
                    "local": combo.local,
                    "nombre": combo.nombre,
                    "medida": combo.medida,
                    "motivo": "No se encontro par colchon+box con misma medida",
                }
            )
            continue

        colchon_item, box_item = pair
        # validar medidas
        med_c = colchon_item.n_medida or combo_med_norm
        med_b = box_item.n_medida or combo_med_norm
        if med_c and med_b and med_c != med_b:
            reviews.append(
                {
                    "combo_id": combo.id,
                    "local": combo.local,
                    "nombre": combo.nombre,
                    "medida": combo.medida,
                    "motivo": "Par colchon/box sin misma medida",
                }
            )
            continue

        colchon_name = colchon_item.nombre.strip()
        if not _is_colchon_text(colchon_name):
            colchon_name = f"colchon {colchon_name}".strip()
        new_nombre = f"conjunto {colchon_name}".strip()
        new_categoria = "conjuntos"

        fixes.append(
            {
                "combo_id": combo.id,
                "local": combo.local,
                "old_nombre": combo.nombre,
                "new_nombre": new_nombre,
                "old_categoria": combo.categoria,
                "new_categoria": new_categoria,
                "medida": combo.medida,
                "colchon_id": colchon_item.producto_id,
                "colchon_nombre": colchon_item.nombre,
                "box_id": box_item.producto_id,
                "box_nombre": box_item.nombre,
                "fallback": int(fallback_used),
            }
        )

        if apply:
            # update combo product
            cur.execute(
                f"UPDATE productos SET nombre={ph}, categoria={ph} WHERE id={ph}",
                (new_nombre, new_categoria, combo.id),
            )
            # reset combo items to exactly 2 (colchon + box), qty=1
            cur.execute(
                f"DELETE FROM combo_items WHERE combo_producto_id={ph}", (combo.id,)
            )
            for it in (colchon_item, box_item):
                cur.execute(
                    f"""
                    INSERT INTO combo_items (
                        combo_producto_id, producto_id, cantidad,
                        producto_nombre, producto_categoria, producto_medida,
                        producto_estado, producto_color, producto_fabricante
                    ) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                    """,
                    (
                        combo.id,
                        it.producto_id,
                        1,
                        it.nombre,
                        it.categoria,
                        it.medida,
                        it.estado,
                        it.color,
                        it.fabricante,
                    ),
                )

    if apply:
        conn.commit()
    conn.close()

    ts = _now()
    out_dir = Path("exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    fix_path = out_dir / f"fix_colchon_combos_{ts}.csv"
    review_path = out_dir / f"fix_colchon_combos_review_{ts}.csv"

    if fixes:
        with fix_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(fixes[0].keys()))
            w.writeheader()
            w.writerows(fixes)

    if reviews:
        with review_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(reviews[0].keys()))
            w.writeheader()
            w.writerows(reviews)

    print(f"Fixes: {len(fixes)}")
    print(f"Review: {len(reviews)}")
    if fixes:
        print(f"Reporte fixes: {fix_path}")
    if reviews:
        print(f"Reporte review: {review_path}")


if __name__ == "__main__":
    main()
