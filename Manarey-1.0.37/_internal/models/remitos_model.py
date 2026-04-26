import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle


def _fmt_datetime(value) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if "." in s:
        s = s.split(".")[0]
    s = s.replace("T", " ")
    return s


def _fmt_money(value) -> str:
    try:
        return "{:,}".format(int(value)).replace(",", ".")
    except Exception:
        return str(value or 0)


def _safe_str(value) -> str:
    return str(value or "").strip()


def _draw_remito(
    c: canvas.Canvas, venta: dict, *, top_y: float, bottom_y: float
) -> None:
    page_w, _ = A4
    margin = 14 * mm
    min_y = bottom_y + (10 * mm)

    y = top_y - margin
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "REMITO DE ENVIO")
    c.setFont("Helvetica", 10)
    c.drawRightString(
        page_w - margin,
        y,
        f"Fecha: {_fmt_datetime(venta.get('fecha') or datetime.now())}",
    )

    y -= 18
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, f"Venta Nro: {venta.get('numero_venta', '')}")

    # Datos del cliente
    y -= 18
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Cliente")
    y -= 14
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, f"Nombre: {_safe_str(venta.get('cliente_nombre'))}")
    y -= 12
    c.drawString(margin, y, f"Telefono: {_safe_str(venta.get('cliente_telefono'))}")
    y -= 12
    calle = _safe_str(venta.get("cliente_calle"))
    numero = _safe_str(venta.get("cliente_numero"))
    localidad = _safe_str(venta.get("cliente_localidad"))
    direccion = " ".join(p for p in [calle, numero] if p)
    if localidad:
        direccion = f"{direccion} - {localidad}" if direccion else localidad
    c.drawString(margin, y, f"Direccion: {direccion}")
    entre = _safe_str(venta.get("entre_calles"))
    if entre:
        y -= 12
        c.drawString(margin, y, f"Entre calles: {entre}")

    # Pago envio en local / checkboxes
    y -= 18
    forma_envio = _safe_str(venta.get("forma_pago_envio"))
    monto_envio = venta.get("precio_envio", 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Pago del envio")
    y -= 14
    c.setFont("Helvetica", 10)
    if forma_envio:
        forma_envio_norm = forma_envio.strip().lower()
        if forma_envio_norm in ("local", "en local"):
            c.setFont("Helvetica-Bold", 12)
            c.setFillColor(colors.darkgreen)
            c.drawString(margin, y, "ENVIO PAGADO EN LOCAL")
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 10)
        elif forma_envio_norm in ("domicilio", "en domicilio"):
            c.drawString(margin, y, f"Monto de envio: ${_fmt_money(monto_envio)}")
            y -= 12
            c.drawString(margin, y, "Pago de envio: En domicilio")
        else:
            c.drawString(margin, y, f"Envio pagado en local: {forma_envio}")
    else:
        c.drawString(margin, y, f"Monto de envio: ${_fmt_money(monto_envio)}")
        y -= 12
        c.drawString(margin, y, "No abonado en local. Marcar al entregar:")
        y -= 14
        box = 10
        c.rect(margin, y - 2, box, box, stroke=1, fill=0)
        c.drawString(margin + box + 6, y, "Transferencia")
        c.rect(margin + 120, y - 2, box, box, stroke=1, fill=0)
        c.drawString(margin + 120 + box + 6, y, "Efectivo")

    # Si paga en domicilio, mostrar lo que hay que cobrar
    tipo_pago = _safe_str(venta.get("tipo_pago")).lower()
    if tipo_pago == "domicilio":
        y -= 20
        monto = venta.get("monto_pendiente")
        if monto in (None, ""):
            monto = venta.get("total")
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.red)
        c.drawString(margin, y, f"COBRAR EN DOMICILIO: ${_fmt_money(monto)}")
        c.setFillColor(colors.black)

    # Productos
    y -= 24
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Productos")
    y -= 6

    items = venta.get("items") or []
    # Incluir columna Color
    data = [
        ["Nombre", "Categoria", "Color", "Fabricante", "Medida", "Estado", "Cantidad"]
    ]
    for it in items:
        nombre = _safe_str(it.get("producto_nombre") or it.get("nombre"))
        categoria = _safe_str(it.get("producto_categoria") or it.get("categoria"))
        color = _safe_str(it.get("producto_color") or it.get("color"))
        fabricante = _safe_str(
            it.get("producto_fabricante") or it.get("fabricante") or "-"
        )
        medida = _safe_str(it.get("producto_medida") or it.get("medida"))
        estado = _safe_str(it.get("producto_estado") or it.get("estado"))
        cantidad = str(it.get("cantidad") or "")
        data.append([nombre, categoria, color, fabricante, medida, estado, cantidad])

    available_w = page_w - (margin * 2)
    # Ajustar pesos para la columna adicional Color
    col_weights = [0.26, 0.13, 0.09, 0.13, 0.11, 0.18, 0.10]
    col_widths = [available_w * w for w in col_weights]
    table = Table(data, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    tw, th = table.wrapOn(c, page_w - (margin * 2), y)
    table.drawOn(c, margin, max(min_y, y - th))

    # Firmas
    sig_y = max(min_y + 20, y - th - 120)
    c.setFont("Helvetica", 10)
    c.line(margin, sig_y, margin + 200, sig_y)
    c.drawString(margin, sig_y - 12, "Firma cliente (entregado)")
    c.line(page_w - margin - 200, sig_y, page_w - margin, sig_y)
    c.drawString(page_w - margin - 200, sig_y - 12, "Firma repartidor")


def generar_remito_pdf(venta: dict, out_path: str) -> tuple:
    """
    Genera un remito de envio sin precios, salvo que sea pago en domicilio.
    """
    try:
        c = canvas.Canvas(out_path, pagesize=A4)
        _, page_h = A4
        _draw_remito(c, venta, top_y=page_h, bottom_y=0)
        c.save()
        return True, out_path
    except Exception as e:
        return False, str(e)


def _calc_remito_height(venta: dict, page_w: float) -> float:
    margin = 14 * mm
    y = 0.0
    y -= margin
    y -= 18
    y -= 18
    y -= 14
    y -= 12
    y -= 12
    y -= 12
    entre = _safe_str(venta.get("entre_calles"))
    if entre:
        y -= 12
    y -= 18
    y -= 14

    forma_envio = _safe_str(venta.get("forma_pago_envio"))
    if forma_envio:
        forma_envio_norm = forma_envio.strip().lower()
        if forma_envio_norm in ("domicilio", "en domicilio"):
            y -= 12
    else:
        y -= 12
        y -= 14

    tipo_pago = _safe_str(venta.get("tipo_pago")).lower()
    if tipo_pago == "domicilio":
        y -= 20

    y -= 24
    y -= 6

    items = venta.get("items") or []
    data = [
        ["Nombre", "Categoria", "Color", "Fabricante", "Medida", "Estado", "Cantidad"]
    ]
    for it in items:
        nombre = _safe_str(it.get("producto_nombre") or it.get("nombre"))
        categoria = _safe_str(it.get("producto_categoria") or it.get("categoria"))
        color = _safe_str(it.get("producto_color") or it.get("color"))
        fabricante = _safe_str(
            it.get("producto_fabricante") or it.get("fabricante") or "-"
        )
        medida = _safe_str(it.get("producto_medida") or it.get("medida"))
        estado = _safe_str(it.get("producto_estado") or it.get("estado"))
        cantidad = str(it.get("cantidad") or "")
        data.append([nombre, categoria, color, fabricante, medida, estado, cantidad])

    available_w = page_w - (margin * 2)
    col_weights = [0.26, 0.13, 0.09, 0.13, 0.11, 0.18, 0.10]
    col_widths = [available_w * w for w in col_weights]
    table = Table(data, colWidths=col_widths)
    _, th = table.wrapOn(canvas.Canvas(os.devnull), available_w, 0)

    y -= th
    y -= 52
    y -= 10
    return abs(y)


def _draw_cut_line(c: canvas.Canvas, y: float) -> None:
    page_w, _ = A4
    margin = 14 * mm
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.8)
    c.setDash(3, 3)
    c.line(margin, y, page_w - margin, y)
    c.setDash()
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.grey)
    c.drawString((page_w / 2) - 20, y + 2, "Cortar aqui")
    c.setFillColor(colors.black)


def generar_remitos_pdf(ventas: list, out_path: str) -> tuple:
    if not ventas:
        return False, "No hay remitos para imprimir"
    try:
        c = canvas.Canvas(out_path, pagesize=A4)
        page_w, page_h = A4
        min_bottom = 10 * mm
        sep_h = 8 * mm
        heights = [_calc_remito_height(v, page_w) for v in ventas]
        y_top = page_h

        for idx, venta in enumerate(ventas):
            req_h = heights[idx]
            if (y_top - req_h) < min_bottom:
                c.showPage()
                y_top = page_h

            bottom_y = y_top - req_h
            _draw_remito(c, venta, top_y=y_top, bottom_y=bottom_y)
            y_top = bottom_y

            if idx < len(ventas) - 1:
                next_h = heights[idx + 1]
                if (y_top - sep_h - next_h) < min_bottom:
                    c.showPage()
                    y_top = page_h
                else:
                    _draw_cut_line(c, y_top - (sep_h / 2))
                    y_top -= sep_h
        c.save()
        return True, out_path
    except Exception as e:
        return False, str(e)
