import csv
import math
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

from models import db


def _norm_text(val):
    if val is None:
        return ""
    s = str(val)
    s = s.strip().lower()
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


def _sim(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _price_close(a, b, abs_tol, rel_tol):
    try:
        a = float(a or 0)
        b = float(b or 0)
    except Exception:
        return True
    if a <= 0 or b <= 0:
        return True
    diff = abs(a - b)
    if diff <= abs_tol:
        return True
    base = max(a, b)
    if base <= 0:
        return True
    return (diff / base) <= rel_tol


def _price_diff(a, b):
    try:
        a = float(a or 0)
        b = float(b or 0)
    except Exception:
        return 0.0, 0.0
    diff = abs(a - b)
    base = max(a, b)
    rel = (diff / base) if base > 0 else 0.0
    return diff, rel


def _get_columns(cur):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='productos'"
    )
    return {r[0] for r in cur.fetchall()}


def _get_combo_table_exists(cur):
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name='combo_items'"
    )
    return cur.fetchone() is not None


def _load_products(cur, cols):
    wanted = [
        "id",
        "nombre",
        "material",
        "categoria",
        "medida",
        "estado",
        "color",
        "fabricante",
        "codigo",
        "descripcion",
        "precio_costo",
        "precio_venta",
        "cantidad",
        "local",
        "is_combo",
        "created_at",
        "updated_at",
    ]
    select_cols = []
    for c in wanted:
        if c in cols:
            select_cols.append(c)
        else:
            select_cols.append("NULL AS " + c)
    cur.execute("SELECT " + ", ".join(select_cols) + " FROM productos")
    rows = cur.fetchall()
    out = []
    for r in rows:
        row = dict(zip(wanted, r))
        out.append(row)
    return out


def _load_combo_items(cur):
    cur.execute(
        """
        SELECT combo_producto_id, cantidad,
               COALESCE(producto_nombre,''), COALESCE(producto_categoria,''), COALESCE(producto_medida,''),
               COALESCE(producto_estado,''), COALESCE(producto_color,''), COALESCE(producto_fabricante,'')
        FROM combo_items
        """
    )
    items = defaultdict(list)
    for row in cur.fetchall():
        combo_id = row[0]
        items[combo_id].append(
            {
                "cantidad": row[1],
                "nombre": row[2],
                "categoria": row[3],
                "medida": row[4],
                "estado": row[5],
                "color": row[6],
                "fabricante": row[7],
            }
        )
    return items


def _items_signature(items):
    if not items:
        return "", set()
    parts = []
    for it in items:
        seg = [
            _norm_text(it.get("nombre")),
            _norm_text(it.get("categoria")),
            _norm_text(it.get("medida")),
            _norm_text(it.get("estado")),
            _norm_text(it.get("color")),
            _norm_text(it.get("fabricante")),
        ]
        qty = int(it.get("cantidad") or 0)
        parts.append("|".join(seg) + f":{qty}")
    parts.sort()
    sig = ",".join(parts)
    return sig, set(parts)


def _exact_key(p):
    return (
        _norm_text(p.get("nombre")),
        _norm_text(p.get("material")),
        _norm_text(p.get("categoria")),
        _norm_text(p.get("medida")),
        _norm_text(p.get("estado")),
        _norm_text(p.get("color")),
        _norm_text(p.get("fabricante")),
        _norm_text(p.get("codigo")),
        _norm_text(p.get("descripcion")),
        float(p.get("precio_costo") or 0),
        float(p.get("precio_venta") or 0),
        int(p.get("is_combo") or 0),
        p.get("items_sig", ""),
    )


def _score_pair(a, b, price_abs, price_rel, combo_items_weight=2.0):
    name_sim = _sim(a["n_nombre"], b["n_nombre"])
    cat_sim = _sim(a["n_categoria"], b["n_categoria"])
    med_sim = _sim(a["n_medida"], b["n_medida"])
    est_sim = _sim(a["n_estado"], b["n_estado"])
    col_sim = _sim(a["n_color"], b["n_color"])
    mat_sim = _sim(a["n_material"], b["n_material"])
    fab_sim = _sim(a["n_fabricante"], b["n_fabricante"])
    cod_sim = _sim(a["n_codigo"], b["n_codigo"])
    des_sim = _sim(a["n_descripcion"], b["n_descripcion"])

    items_sim = 1.0
    if a.get("items_sig") or b.get("items_sig"):
        items_sim = _sim(a.get("items_sig", ""), b.get("items_sig", ""))

    weights = {
        "nombre": 3.0,
        "categoria": 2.0,
        "medida": 1.0,
        "estado": 1.0,
        "color": 1.0,
        "material": 1.0,
        "fabricante": 1.0,
        "codigo": 1.0,
        "descripcion": 0.5,
        "items": combo_items_weight
        if (a.get("is_combo") or b.get("is_combo"))
        else 0.0,
    }
    total_w = sum(weights.values())
    score = (
        name_sim * weights["nombre"]
        + cat_sim * weights["categoria"]
        + med_sim * weights["medida"]
        + est_sim * weights["estado"]
        + col_sim * weights["color"]
        + mat_sim * weights["material"]
        + fab_sim * weights["fabricante"]
        + cod_sim * weights["codigo"]
        + des_sim * weights["descripcion"]
        + items_sim * weights["items"]
    ) / (total_w or 1.0)

    price_ok = _price_close(
        a.get("precio_venta"), b.get("precio_venta"), price_abs, price_rel
    )
    cost_ok = _price_close(
        a.get("precio_costo"), b.get("precio_costo"), price_abs, price_rel
    )
    return {
        "score": score,
        "name_sim": name_sim,
        "cat_sim": cat_sim,
        "med_sim": med_sim,
        "est_sim": est_sim,
        "col_sim": col_sim,
        "mat_sim": mat_sim,
        "fab_sim": fab_sim,
        "cod_sim": cod_sim,
        "des_sim": des_sim,
        "items_sim": items_sim,
        "price_ok": price_ok,
        "cost_ok": cost_ok,
    }


def main():
    price_abs = 100.0
    price_rel = 0.05
    name_min = 0.90
    score_min = 0.88
    cat_min = 0.80
    if len(sys.argv) > 1:
        try:
            price_abs = float(sys.argv[1])
        except Exception:
            pass
    if len(sys.argv) > 2:
        try:
            price_rel = float(sys.argv[2])
        except Exception:
            pass

    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cols = _get_columns(cur)
        products = _load_products(cur, cols)
        combo_items = {}
        if _get_combo_table_exists(cur):
            combo_items = _load_combo_items(cur)
    finally:
        db.put_connection(conn)

    for p in products:
        pid = int(p.get("id") or 0)
        p["items_sig"] = ""
        p["items_set"] = set()
        if int(p.get("is_combo") or 0) == 1 and pid in combo_items:
            sig, sset = _items_signature(combo_items.get(pid))
            p["items_sig"] = sig
            p["items_set"] = sset

        p["n_nombre"] = _norm_text(p.get("nombre"))
        p["n_material"] = _norm_text(p.get("material"))
        p["n_categoria"] = _norm_text(p.get("categoria"))
        p["n_medida"] = _norm_text(p.get("medida"))
        p["n_estado"] = _norm_text(p.get("estado"))
        p["n_color"] = _norm_text(p.get("color"))
        p["n_fabricante"] = _norm_text(p.get("fabricante"))
        p["n_codigo"] = _norm_text(p.get("codigo"))
        p["n_descripcion"] = _norm_text(p.get("descripcion"))

    # Buckets for candidate generation
    buckets = defaultdict(list)
    for idx, p in enumerate(products):
        name = p["n_nombre"]
        cat = p["n_categoria"]
        code = p["n_codigo"]
        key1 = ("namecat", name[:4], cat)
        buckets[key1].append(idx)
        if code:
            buckets[("code", code)].append(idx)

    seen_pairs = set()
    results = []

    def _pair_key(i, j):
        return (i, j) if i < j else (j, i)

    for bkey, idxs in buckets.items():
        if len(idxs) <= 1:
            continue
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                a_idx = idxs[i]
                b_idx = idxs[j]
                pk = _pair_key(a_idx, b_idx)
                if pk in seen_pairs:
                    continue
                seen_pairs.add(pk)
                a = products[a_idx]
                b = products[b_idx]
                if a.get("id") == b.get("id"):
                    continue
                if _exact_key(a) == _exact_key(b):
                    continue
                score = _score_pair(a, b, price_abs, price_rel)
                if score["name_sim"] < name_min:
                    continue
                if score["cat_sim"] < cat_min and a["n_categoria"] and b["n_categoria"]:
                    continue
                if not (score["price_ok"] and score["cost_ok"]):
                    continue
                if score["score"] < score_min:
                    continue

                results.append((a, b, score))

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"exports/similares_{now}.csv"

    headers = [
        "tipo",
        "score",
        "name_sim",
        "cat_sim",
        "med_sim",
        "est_sim",
        "col_sim",
        "mat_sim",
        "fab_sim",
        "cod_sim",
        "des_sim",
        "items_sim",
        "precio_diff",
        "precio_rel",
        "costo_diff",
        "costo_rel",
        "id1",
        "local1",
        "nombre1",
        "categoria1",
        "medida1",
        "estado1",
        "color1",
        "material1",
        "fabricante1",
        "codigo1",
        "descripcion1",
        "precio_venta1",
        "precio_costo1",
        "cantidad1",
        "is_combo1",
        "items_sig1",
        "id2",
        "local2",
        "nombre2",
        "categoria2",
        "medida2",
        "estado2",
        "color2",
        "material2",
        "fabricante2",
        "codigo2",
        "descripcion2",
        "precio_venta2",
        "precio_costo2",
        "cantidad2",
        "is_combo2",
        "items_sig2",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for a, b, sc in sorted(results, key=lambda x: x[2]["score"], reverse=True):
            precio_diff, precio_rel = _price_diff(
                a.get("precio_venta"), b.get("precio_venta")
            )
            costo_diff, costo_rel = _price_diff(
                a.get("precio_costo"), b.get("precio_costo")
            )
            row = [
                "combo"
                if (
                    int(a.get("is_combo") or 0) == 1 or int(b.get("is_combo") or 0) == 1
                )
                else "producto",
                round(sc["score"], 4),
                round(sc["name_sim"], 4),
                round(sc["cat_sim"], 4),
                round(sc["med_sim"], 4),
                round(sc["est_sim"], 4),
                round(sc["col_sim"], 4),
                round(sc["mat_sim"], 4),
                round(sc["fab_sim"], 4),
                round(sc["cod_sim"], 4),
                round(sc["des_sim"], 4),
                round(sc["items_sim"], 4),
                round(precio_diff, 2),
                round(precio_rel, 4),
                round(costo_diff, 2),
                round(costo_rel, 4),
                a.get("id"),
                a.get("local"),
                a.get("nombre"),
                a.get("categoria"),
                a.get("medida"),
                a.get("estado"),
                a.get("color"),
                a.get("material"),
                a.get("fabricante"),
                a.get("codigo"),
                a.get("descripcion"),
                a.get("precio_venta"),
                a.get("precio_costo"),
                a.get("cantidad"),
                a.get("is_combo"),
                a.get("items_sig"),
                b.get("id"),
                b.get("local"),
                b.get("nombre"),
                b.get("categoria"),
                b.get("medida"),
                b.get("estado"),
                b.get("color"),
                b.get("material"),
                b.get("fabricante"),
                b.get("codigo"),
                b.get("descripcion"),
                b.get("precio_venta"),
                b.get("precio_costo"),
                b.get("cantidad"),
                b.get("is_combo"),
                b.get("items_sig"),
            ]
            writer.writerow(row)

    print(f"Productos analizados: {len(products)}")
    print(f"Pares similares detectados: {len(results)}")
    print(f"Reporte: {out_path}")


if __name__ == "__main__":
    main()
