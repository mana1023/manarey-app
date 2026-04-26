# models/boletas_model.py - PDF MEJORADO VERSIÓN FINAL
import json
import os
from decimal import ROUND_HALF_UP, Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

from config import (
    PDF_LOGO_FALLBACK,
    PDF_LOGO_POSITION,
    PDF_LOGO_PRIMARY,
    PDF_LOGO_WIDTH_PT,
    PDF_LOGO_Y_OFFSET,
)
from models import db as db_mod


def format_money(value):
    """Formatea valores monetarios"""
    from utils.money import format_money_es

    try:
        return format_money_es(value)
    except Exception:
        return f"${value}"


def _fmt_date_only(value) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if "." in s:
        s = s.split(".")[0]
    s = s.replace("T", " ")
    date_part = s.split(" ")[0]
    if len(date_part) >= 10 and date_part[4] == "-" and date_part[7] == "-":
        y, m, d = date_part[0:4], date_part[5:7], date_part[8:10]
        return f"{d}-{m}-{y}"
    return date_part


def _fmt_datetime(value) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if "." in s:
        s = s.split(".")[0]
    s = s.replace("T", " ")
    parts = s.split(" ")
    date_part = _fmt_date_only(parts[0]) if parts else _fmt_date_only(s)
    time_part = parts[1] if len(parts) > 1 else ""
    return f"{date_part} {time_part}".strip()


def _load_config() -> dict:
    for p in db_mod.CONFIG_PATHS:
        try:
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _get_local_contact(local_name: str) -> tuple[str, str]:
    local_key = (local_name or "").strip().lower()
    if not local_key:
        return "", ""
    cfg = _load_config()
    info = cfg.get("locales_info", {}) if isinstance(cfg, dict) else {}
    if not isinstance(info, dict):
        return "", ""
    for k, v in info.items():
        try:
            if (k or "").strip().lower() == local_key:
                direccion = (
                    (v or {}).get("direccion", "") if isinstance(v, dict) else ""
                )
                telefono = (v or {}).get("telefono", "") if isinstance(v, dict) else ""
                return direccion or "", telefono or ""
        except Exception:
            continue
    return "", ""


def generar_boleta_pdf_a4_duplicada(boleta: dict, out_path: str) -> tuple:
    """
    Genera PDF A4 con dos copias:
    - COPIA SUPERIOR: Para el local (solo datos básicos)
    - COPIA INFERIOR: Para el cliente (con todos los datos + sucursales)
    """
    try:
        page_w, page_h = A4
        margin = 15 * mm
        half_h = page_h / 2.0

        c = canvas.Canvas(out_path, pagesize=A4)

        # Colores corporativos
        COLOR_DORADO = colors.Color(201 / 255, 160 / 255, 64 / 255)
        COLOR_DARK = colors.Color(31 / 255, 31 / 255, 34 / 255)
        COLOR_BORDER = colors.Color(52 / 255, 52 / 255, 58 / 255)
        COLOR_SUCCESS = colors.Color(76 / 255, 175 / 255, 80 / 255)
        COLOR_WARNING = colors.Color(255 / 255, 152 / 255, 0 / 255)
        COLOR_INFO = colors.Color(33 / 255, 150 / 255, 243 / 255)

        def draw_mitad(
            y_base, es_copia_cliente=False, detalle_subset=None, show_totals=True
        ):
            """Dibuja una mitad de la boleta"""
            x_start = margin
            x_end = page_w - margin
            ancho_util = x_end - x_start
            y_top = y_base
            # Estado de pago (para usar en toda la mitad)
            pago = boleta.get("pago", {})
            tipo_pago = pago.get("tipo_abono", "").lower()
            es_credito_personal = "credito_personal" in tipo_pago

            # ============ ENCABEZADO ============
            # Borde decorativo superior
            c.setStrokeColor(COLOR_DORADO)
            c.setLineWidth(2)
            c.line(x_start, y_top - 5, x_end, y_top - 5)

            # Logo según configuración
            title_x_offset = 110
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_candidates = [
                os.path.join(project_root, *PDF_LOGO_PRIMARY),
                os.path.join(project_root, *PDF_LOGO_FALLBACK),
            ]
            logo_path = next((p for p in logo_candidates if os.path.exists(p)), None)
            if logo_path and PDF_LOGO_POSITION == "header-left":
                try:
                    img = ImageReader(logo_path)
                    iw, ih = img.getSize()
                    target_w = float(PDF_LOGO_WIDTH_PT)
                    aspect = ih / float(iw) if iw else 0.24
                    target_h = max(20.0, target_w * aspect)
                    c.drawImage(
                        img,
                        x_start + 5,
                        y_top - (target_h + 6),
                        width=target_w,
                        height=target_h,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                    title_x_offset = int(target_w) + 30
                except:
                    pass

            # Número de boleta
            c.setFont("Helvetica-Bold", 14)
            c.setFillColor(COLOR_DORADO)
            c.drawString(
                x_start + title_x_offset,
                y_top - 20,
                f"BOLETA Nº {boleta.get('numero_boleta', 'N/A')}",
            )

            # Fecha
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.black)
            c.drawRightString(
                x_end - 5,
                y_top - 20,
                f"Fecha: {_fmt_datetime(boleta.get('fecha_emision', ''))}",
            )
            c.drawRightString(
                x_end - 5, y_top - 32, f"Local venta: {boleta.get('local', '')}"
            )
            c.drawRightString(
                x_end - 5, y_top - 32, f"Local venta: {boleta.get('local', '')}"
            )

            # Tipo de copia
            c.setFont("Helvetica-Bold", 10)
            if es_copia_cliente and not es_credito_personal:
                c.setFillColor(COLOR_SUCCESS)
                c.drawString(x_start + 110, y_top - 32, "COPIA CLIENTE")
            else:
                c.setFillColor(COLOR_INFO)
                c.drawString(x_start + 110, y_top - 32, "COPIA LOCAL")

            y_cursor = y_top - 60

            # ============ DATOS DEL CLIENTE (en ambas copias) ============
            cliente = boleta.get("cliente", {})

            # Determinar ancho del box de cliente según si es copia cliente o local
            if es_copia_cliente:
                # Reducir un poco para dar m?s espacio al box de pago
                cliente_box_width = ancho_util * 0.52
            else:
                # En copia local, usar menos ancho para dejar espacio al box de pago
                cliente_box_width = ancho_util * 0.52

            # Box cliente con borde
            c.setStrokeColor(COLOR_BORDER)
            c.setLineWidth(1)
            c.roundRect(
                x_start, y_cursor - 58, cliente_box_width, 55, 4, stroke=1, fill=0
            )

            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(x_start + 5, y_cursor - 10, "DATOS DEL CLIENTE:")

            c.setFont("Helvetica", 8)
            y_cliente = y_cursor - 22

            # Nombre
            nombre = cliente.get("nombre", "N/A")
            c.drawString(x_start + 5, y_cliente, f"• {nombre}")

            # Teléfono
            telefono = cliente.get("telefono", "N/A")
            c.drawString(x_start + 5, y_cliente - 10, f"• Tel: {telefono}")

            # Dirección completa (incluyendo entre calles si hay envío)
            partes_direccion = []
            if cliente.get("calle"):
                partes_direccion.append(cliente.get("calle"))
            if cliente.get("numero"):
                partes_direccion.append(cliente.get("numero"))
            if cliente.get("localidad"):
                partes_direccion.append(cliente.get("localidad"))

            # Agregar entre calles a la dirección si hay envío
            if boleta.get("precio_envio", 0) > 0 and cliente.get("entre_calles"):
                entre_calles = cliente.get("entre_calles")
                partes_direccion.append(f"(entre {entre_calles})")

            if partes_direccion:
                direccion = ", ".join(partes_direccion)
                # Dividir dirección si es muy larga
                if len(direccion) > 50:
                    c.drawString(x_start + 5, y_cliente - 20, f"• {direccion[:50]}")
                    c.drawString(x_start + 5, y_cliente - 30, f"  {direccion[50:]}")
                else:
                    c.drawString(x_start + 5, y_cliente - 20, f"• {direccion}")

            y_cursor -= 62

            # ============ ESTADO DE PAGO (DESTACADO) ============
            pago = boleta.get("pago", {})
            tipo_pago = pago.get("tipo_abono", "").lower()
            es_credito_personal = "credito_personal" in tipo_pago
            interes_monto = pago.get("tarjeta_interes_monto", 0) or 0
            interes_pct = pago.get("tarjeta_interes_pct", 0) or 0

            # Box de pago - posicionado a la derecha del box de cliente
            if es_copia_cliente:
                box_pago_x = x_start + (ancho_util * 0.54)
                box_pago_w = ancho_util * 0.44
            else:
                # En copia local, posicionar a la derecha del box de cliente m?s peque?o
                box_pago_x = x_start + (ancho_util * 0.54)
                box_pago_w = ancho_util * 0.44
            if es_credito_personal:
                color_pago = COLOR_DORADO
                estado_texto = "CREDITO PERSONAL"
                detalle_pago = ""
                detalle_pago2 = ""
            elif "se?a" in tipo_pago or "sena" in tipo_pago:
                color_pago = COLOR_WARNING
                estado_texto = "SE?A PAGADA"
                monto_sena = pago.get("monto_sena", 0)
                monto_restante = pago.get("monto_restante", 0)
                detalle_pago = f"Se?a: {format_money(monto_sena)}"
                detalle_pago2 = f"Resta: {format_money(monto_restante)}"
            elif "domicilio" in tipo_pago:
                color_pago = COLOR_INFO
                estado_texto = "PAGO EN DOMICILIO"
                detalle_pago = f"Total a cobrar:"
                detalle_pago2 = f"{format_money(boleta.get('total', 0))}"
            else:
                color_pago = COLOR_SUCCESS
                estado_texto = "PAGO COMPLETO"
                detalle_pago = f"Total pagado:"
                detalle_pago2 = f"{format_money(boleta.get('total', 0))}"

            c.setFillColor(color_pago)
            c.setStrokeColor(color_pago)
            c.setLineWidth(2)
            box_pago_h = 70
            c.roundRect(
                box_pago_x, y_cursor + 5, box_pago_w, box_pago_h, 6, stroke=1, fill=0
            )

            # Texto del estado
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(color_pago)
            c.drawString(box_pago_x + 8, y_cursor + 55, estado_texto)

            # Detalle del pago
            if not es_credito_personal:
                c.setFont("Helvetica", 8)
                c.setFillColor(colors.black)
                c.drawString(box_pago_x + 8, y_cursor + 40, detalle_pago)
                c.setFont("Helvetica-Bold", 9)
                c.drawString(box_pago_x + 8, y_cursor + 30, detalle_pago2)

                # Forma(s) de pago
                c.setFont("Helvetica", 8)
                formas_list = pago.get("formas") or []
                if formas_list:
                    try:
                        breakdown = " | ".join(
                            [
                                f"{str(f.get('forma') or '')}: {format_money(f.get('monto') or 0)}"
                                for f in formas_list
                            ][:3]
                        )
                    except Exception:
                        breakdown = " | ".join(
                            [f"{str(f[0])}: {format_money(f[1])}" for f in formas_list][
                                :3
                            ]
                        )
                    c.drawString(box_pago_x + 8, y_cursor + 18, f"Formas: {breakdown}")
                else:
                    forma_pago = pago.get("forma_pago", "N/A")
                    c.drawString(box_pago_x + 8, y_cursor + 18, f"Forma: {forma_pago}")
                # Interes aplicado a tarjeta (resumen corto)
                try:
                    if interes_monto > 0:
                        label = f"Interes tarjeta ({int(interes_pct)}%): {format_money(interes_monto)}"
                        c.drawString(box_pago_x + 8, y_cursor + 6, label)
                except Exception:
                    pass

            y_cursor -= 10

            # ============ TABLA DE PRODUCTOS ============
            detalle = detalle_subset or []

            # Encabezados (producto con info combinada)
            if es_credito_personal:
                rows = [["Cant", "Producto", "Stock/Retiro"]]
            else:
                rows = [["Cant", "Producto", "Stock/Retiro", "P.Unit", "Subtotal"]]

            # Agregar productos
            for item in detalle:
                producto_info = item.get("producto_nombre", "N/A")
                parts = []
                # categoria no se muestra en boleta
                if item.get("producto_material"):
                    parts.append(item.get("producto_material", ""))
                if item.get("producto_color") or item.get("color"):
                    parts.append(item.get("producto_color") or item.get("color"))
                if item.get("producto_medida"):
                    parts.append(item.get("producto_medida", ""))
                # estado no se muestra en boleta
                if parts:
                    producto_info += f" ({' - '.join([p for p in parts if p])})"
                venta_local = (boleta.get("local") or "").strip()
                stock_local = (item.get("stock_local") or "").strip()
                stock_label = stock_local or venta_local
                if es_credito_personal:
                    rows.append(
                        [
                            str(item.get("cantidad", 0)),
                            producto_info,
                            stock_label,
                        ]
                    )
                else:
                    rows.append(
                        [
                            str(item.get("cantidad", 0)),
                            producto_info,
                            stock_label,
                            format_money(item.get("precio_unitario", 0)),
                            format_money(item.get("subtotal", 0)),
                        ]
                    )

            # Linea separadora
            rows.append([""] * len(rows[0]))

            # ============ SECCION DE TOTALES ============
            subtotal_productos = boleta.get("subtotal", 0)
            precio_envio = boleta.get("precio_envio", 0)
            descuento = boleta.get("descuento_monto", 0)
            total = boleta.get("total", 0)
            interes_monto = pago.get("tarjeta_interes_monto", 0) or 0
            interes_pct = pago.get("tarjeta_interes_pct", 0) or 0
            cuotas = pago.get("tarjeta_cuotas", 0) or 0

            if show_totals and not es_credito_personal:
                # Subtotal productos
                rows.append(["", "", "Subtotal:", format_money(subtotal_productos), ""])
                # Envio (si aplica)
                if precio_envio > 0:
                    rows.append(["", "", "+ Envio:", format_money(precio_envio), ""])
                # Descuento (si aplica)
                if descuento > 0:
                    rows.append(
                        ["", "", "- Descuento:", f"-{format_money(descuento)}", ""]
                    )
                if interes_monto > 0:
                    if interes_pct:
                        label = f"Interes tarjeta ({int(interes_pct)}%)"
                    else:
                        label = "Interes tarjeta"
                    rows.append(
                        ["", "", f"+ {label}:", format_money(interes_monto), ""]
                    )
                # Si hay se?a, mostrar desglose
                if "se?a" in tipo_pago or "sena" in tipo_pago:
                    monto_sena = pago.get("monto_sena", 0)
                    monto_restante = pago.get("monto_restante", 0)
                    rows.append([""] * len(rows[0]))
                    rows.append(["", "", "TOTAL:", format_money(total), ""])
                    rows.append(["", "", "- Se?a:", f"-{format_money(monto_sena)}", ""])
                    rows.append(["", "", "= RESTA:", format_money(monto_restante), ""])
                else:
                    rows.append([""] * len(rows[0]))
                    rows.append(["", "", "TOTAL:", format_money(total), ""])

            # Configurar anchos de columna
            if es_credito_personal:
                total_reserved = 35 + 90
                col_widths = [35, ancho_util - total_reserved, 90]
            else:
                total_reserved = 35 + 90 + 80 + 70
                col_widths = [35, ancho_util - total_reserved, 90, 80, 70]

            # Crear tabla
            tabla = Table(rows, colWidths=col_widths)

            # Estilo de la tabla
            style = [
                # Header
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                # Cuerpo
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),  # Cantidad centrada
                ("ALIGN", (2, 1), (2, -1), "CENTER"),  # Stock/Retiro centrado
                # Grid
                ("GRID", (0, 0), (-1, len(detalle)), 0.5, COLOR_BORDER),
                ("LINEBELOW", (0, len(detalle)), (-1, len(detalle)), 1, COLOR_BORDER),
            ]

            if not es_credito_personal:
                style.append(
                    ("ALIGN", (3, 1), (-1, -1), "RIGHT")
                )  # Precios a la derecha

            # Totales en negrita (solo si se muestran totales)
            if show_totals and not es_credito_personal:
                style.append(
                    ("FONTNAME", (2, len(detalle) + 2), (-1, -1), "Helvetica-Bold")
                )
                style.append(("FONTSIZE", (2, -1), (-1, -1), 10))  # TOTAL m?s grande
                # Si hay se?a, destacar la l?nea RESTA
                if "se?a" in tipo_pago or "sena" in tipo_pago:
                    resta_row = len(rows) - 1
                    style.append(
                        ("BACKGROUND", (2, resta_row), (-1, resta_row), COLOR_WARNING)
                    )
                    style.append(
                        ("TEXTCOLOR", (2, resta_row), (-1, resta_row), colors.white)
                    )

            tabla.setStyle(TableStyle(style))

            # Dibujar tabla con manejo de errores
            try:
                tabla_height = tabla.wrapOn(c, ancho_util, half_h)[1]
                tabla.drawOn(c, x_start, y_cursor - tabla_height - 5)
                y_cursor -= tabla_height + 15
            except Exception:
                # Fallback si hay problema renderizando la tabla
                c.setFont("Helvetica", 9)
                c.setFillColor(colors.red)
                c.drawString(
                    x_start,
                    y_cursor - 12,
                    "No fue posible renderizar el detalle completo por su longitud.",
                )
                c.setFillColor(colors.black)
                y_cursor -= 28

            # (Firmas y sucursales movidas al encabezado)

            # ============ LOGO EN PIE SI ASÍ SE CONFIGURA ==========
            try:
                if logo_path and PDF_LOGO_POSITION == "footer-right":
                    img = ImageReader(logo_path)
                    iw, ih = img.getSize()
                    target_w = float(PDF_LOGO_WIDTH_PT)
                    aspect = ih / float(iw) if iw else 0.24
                    target_h = max(20.0, target_w * aspect)
                    borde_y = y_base - half_h + 5
                    x_logo = x_end - target_w
                    y_logo = borde_y + float(PDF_LOGO_Y_OFFSET)
                    c.drawImage(
                        img,
                        x_logo,
                        y_logo,
                        width=target_w,
                        height=target_h,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
            except:
                pass

                # Firmas junto al logo (en pie, encima de la l?nea de corte)
            if not es_credito_personal:
                try:
                    sig_line_w = 100
                    sig_gap = 24
                    borde_y = y_base - half_h + 5
                    sig_y = borde_y + 18
                    # ubicamos a la izquierda del logo del pie
                    sig_x2 = x_end - (float(PDF_LOGO_WIDTH_PT) + 20) - sig_line_w
                    sig_x1 = sig_x2 - sig_gap - sig_line_w
                    c.setStrokeColor(colors.black)
                    c.setLineWidth(1)
                    c.line(sig_x1, sig_y, sig_x1 + sig_line_w, sig_y)
                    c.line(sig_x2, sig_y, sig_x2 + sig_line_w, sig_y)
                    c.setFont("Helvetica", 7)
                    c.setFillColor(colors.black)
                    c.drawString(sig_x1, sig_y - 10, "Firma - Vendedor")
                    c.drawString(sig_x2, sig_y - 10, "Firma - Cliente")

                    # Datos del local a la izquierda de la firma del vendedor
                    local_dir, local_tel = _get_local_contact(boleta.get("local", ""))
                    info_x = sig_x1 - 150
                    c.setFont("Helvetica-Bold", 9)
                    if local_tel:
                        c.drawString(info_x, sig_y + 2, f"📞 {local_tel}")
                    if local_dir:
                        c.drawString(info_x, sig_y - 12, f"📍 {local_dir}")
                except Exception:
                    pass

            # Borde decorativo inferior
            c.setStrokeColor(COLOR_DORADO)
            c.setLineWidth(2)
            borde_y = y_base - half_h + 5
            c.line(x_start, borde_y, x_end, borde_y)

        def draw_copia_full(es_copia_cliente=False, detalle_full=None):
            """Dibuja una copia ocupando la hoja completa (sin dividir en mitades)."""
            x_start = margin
            x_end = page_w - margin
            ancho_util = x_end - x_start
            y_top = page_h - margin

            # Borde decorativo superior
            c.setStrokeColor(COLOR_DORADO)
            c.setLineWidth(2)
            c.line(x_start, y_top - 5, x_end, y_top - 5)

            # Logo
            title_x_offset = 110
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_candidates = [
                os.path.join(project_root, *PDF_LOGO_PRIMARY),
                os.path.join(project_root, *PDF_LOGO_FALLBACK),
            ]
            logo_path = next((p for p in logo_candidates if os.path.exists(p)), None)
            if logo_path and PDF_LOGO_POSITION == "header-left":
                try:
                    img = ImageReader(logo_path)
                    iw, ih = img.getSize()
                    target_w = float(PDF_LOGO_WIDTH_PT)
                    aspect = ih / float(iw) if iw else 0.24
                    target_h = max(20.0, target_w * aspect)
                    c.drawImage(
                        img,
                        x_start + 5,
                        y_top - (target_h + 6),
                        width=target_w,
                        height=target_h,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                    if not es_credito_personal:
                        sig_line_w = 80
                        # Firmas junto al logo (fallback si no hay logo)
                        if not es_credito_personal:
                            try:
                                sig_line_w = 80
                                sig_gap = 16
                                sig_y = y_top - 28
                                base_x = x_start + 120
                                sig_x1 = base_x
                                sig_x2 = sig_x1 + sig_line_w + sig_gap
                                c.setStrokeColor(colors.black)
                                c.setLineWidth(1)
                                c.line(sig_x1, sig_y, sig_x1 + sig_line_w, sig_y)
                                c.line(sig_x2, sig_y, sig_x2 + sig_line_w, sig_y)
                                c.setFont("Helvetica", 7)
                                c.setFillColor(colors.black)
                                c.drawString(sig_x1, sig_y - 10, "Firma - Vendedor")
                                c.drawString(sig_x2, sig_y - 10, "Firma - Cliente")
                                title_x_offset = max(
                                    title_x_offset,
                                    int(sig_x2 + sig_line_w + 20 - x_start),
                                )
                            except Exception:
                                pass

                        sig_gap = 16
                        sig_y = y_top - 28
                        sig_x1 = x_start + 5 + target_w + 10
                        sig_x2 = sig_x1 + sig_line_w + sig_gap
                        c.setStrokeColor(colors.black)
                        c.setLineWidth(1)
                        c.line(sig_x1, sig_y, sig_x1 + sig_line_w, sig_y)
                        c.line(sig_x2, sig_y, sig_x2 + sig_line_w, sig_y)
                        c.setFont("Helvetica", 7)
                        c.setFillColor(colors.black)
                        c.drawString(sig_x1, sig_y - 10, "Firma - Vendedor")
                        c.drawString(sig_x2, sig_y - 10, "Firma - Cliente")
                        title_x_offset = max(
                            title_x_offset, int(sig_x2 + sig_line_w + 20 - x_start)
                        )
                    else:
                        title_x_offset = int(target_w) + 30
                except:
                    pass

            # Número de boleta
            c.setFont("Helvetica-Bold", 14)
            c.setFillColor(COLOR_DORADO)
            c.drawString(
                x_start + title_x_offset,
                y_top - 20,
                f"BOLETA Nº {boleta.get('numero_boleta', 'N/A')}",
            )

            # Fecha
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.black)
            c.drawRightString(
                x_end - 5,
                y_top - 20,
                f"Fecha: {_fmt_datetime(boleta.get('fecha_emision', ''))}",
            )

            # Tipo de copia
            c.setFont("Helvetica-Bold", 10)
            if es_copia_cliente:
                c.setFillColor(COLOR_SUCCESS)
                c.drawString(x_start + 110, y_top - 32, "COPIA CLIENTE")
            else:
                c.setFillColor(COLOR_INFO)
                c.drawString(x_start + 110, y_top - 32, "COPIA LOCAL")

            y_cursor = y_top - 60

            # ============ DATOS DEL CLIENTE ==========
            cliente = boleta.get("cliente", {})
            cliente_box_width = (
                ancho_util * 0.58 if es_copia_cliente else ancho_util * 0.52
            )
            c.setStrokeColor(COLOR_BORDER)
            c.setLineWidth(1)
            c.roundRect(
                x_start, y_cursor - 58, cliente_box_width, 55, 4, stroke=1, fill=0
            )

            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(x_start + 5, y_cursor - 10, "DATOS DEL CLIENTE:")

            c.setFont("Helvetica", 8)
            y_cliente = y_cursor - 22
            nombre = cliente.get("nombre", "N/A")
            c.drawString(x_start + 5, y_cliente, f"• {nombre}")
            telefono = cliente.get("telefono", "N/A")
            c.drawString(x_start + 5, y_cliente - 10, f"• Tel: {telefono}")

            partes_direccion = []
            if cliente.get("calle"):
                partes_direccion.append(cliente.get("calle"))
            if cliente.get("numero"):
                partes_direccion.append(cliente.get("numero"))
            if cliente.get("localidad"):
                partes_direccion.append(cliente.get("localidad"))
            if boleta.get("precio_envio", 0) > 0 and cliente.get("entre_calles"):
                partes_direccion.append(f"(entre {cliente.get('entre_calles')})")
            if partes_direccion:
                direccion = ", ".join(partes_direccion)
                if len(direccion) > 70:
                    c.drawString(x_start + 5, y_cliente - 20, f"• {direccion[:70]}")
                    c.drawString(x_start + 5, y_cliente - 30, f"  {direccion[70:]}")
                else:
                    c.drawString(x_start + 5, y_cliente - 20, f"• {direccion}")

            y_cursor -= 62

            # ============ ESTADO DE PAGO ==========
            pago = boleta.get("pago", {})
            tipo_pago = pago.get("tipo_abono", "").lower()

            es_credito_personal = "credito_personal" in tipo_pago
            interes_monto = pago.get("tarjeta_interes_monto", 0) or 0
            interes_pct = pago.get("tarjeta_interes_pct", 0) or 0

            box_pago_x = (
                x_start + (ancho_util * 0.60)
                if es_copia_cliente
                else x_start + (ancho_util * 0.54)
            )
            box_pago_w = ancho_util * (0.38 if es_copia_cliente else 0.44)
            if es_credito_personal:
                color_pago = COLOR_DORADO
                estado_texto = "CREDITO PERSONAL"
                detalle_pago = ""
                detalle_pago2 = ""
            elif "se?a" in tipo_pago or "sena" in tipo_pago:
                color_pago = COLOR_WARNING
                estado_texto = "SE?A PAGADA"
                monto_sena = pago.get("monto_sena", 0)
                monto_restante = pago.get("monto_restante", 0)
                detalle_pago = f"Se?a: {format_money(monto_sena)}"
                detalle_pago2 = f"Resta: {format_money(monto_restante)}"
            elif "domicilio" in tipo_pago:
                color_pago = COLOR_INFO
                estado_texto = "PAGO EN DOMICILIO"
                detalle_pago = f"Total a cobrar:"
                detalle_pago2 = f"{format_money(boleta.get('total', 0))}"
            else:
                color_pago = COLOR_SUCCESS
                estado_texto = "PAGO COMPLETO"
                detalle_pago = f"Total pagado:"
                detalle_pago2 = f"{format_money(boleta.get('total', 0))}"

            c.setFillColor(color_pago)
            c.setStrokeColor(color_pago)
            c.setLineWidth(2)
            box_pago_h = 70
            c.roundRect(
                box_pago_x, y_cursor + 5, box_pago_w, box_pago_h, 6, stroke=1, fill=0
            )

            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(color_pago)
            c.drawString(box_pago_x + 8, y_cursor + 55, estado_texto)
            if not es_credito_personal:
                c.setFont("Helvetica", 8)
                c.setFillColor(colors.black)
                c.drawString(box_pago_x + 8, y_cursor + 40, detalle_pago)
                c.setFont("Helvetica-Bold", 9)
                c.drawString(box_pago_x + 8, y_cursor + 30, detalle_pago2)
                c.setFont("Helvetica", 8)
                formas_list = pago.get("formas") or []
                if formas_list:
                    try:
                        breakdown = " | ".join(
                            [
                                f"{str(f.get('forma') or '')}: {format_money(f.get('monto') or 0)}"
                                for f in formas_list
                            ][:3]
                        )
                    except Exception:
                        breakdown = " | ".join(
                            [f"{str(f[0])}: {format_money(f[1])}" for f in formas_list][
                                :3
                            ]
                        )
                    c.drawString(box_pago_x + 8, y_cursor + 18, f"Formas: {breakdown}")
                else:
                    c.drawString(
                        box_pago_x + 8,
                        y_cursor + 18,
                        f"Forma: {pago.get('forma_pago', 'N/A')}",
                    )
                # Interes aplicado a tarjeta (resumen corto)
                try:
                    if interes_monto > 0:
                        label = f"Interes tarjeta ({int(interes_pct)}%): {format_money(interes_monto)}"
                        c.drawString(box_pago_x + 8, y_cursor + 6, label)
                except Exception:
                    pass

            y_cursor -= 10

            # ============ TABLA DE PRODUCTOS ==========
            detalle = detalle_full or []
            if es_credito_personal:
                rows = [["Cant", "Producto", "Stock/Retiro"]]
            else:
                rows = [["Cant", "Producto", "Stock/Retiro", "P.Unit", "Subtotal"]]
            for item in detalle:
                producto_info = item.get("producto_nombre", "N/A")
                parts = []
                # categoria no se muestra en boleta
                if item.get("producto_material"):
                    parts.append(item.get("producto_material", ""))
                if item.get("producto_color") or item.get("color"):
                    parts.append(item.get("producto_color") or item.get("color"))
                if item.get("producto_medida"):
                    parts.append(item.get("producto_medida", ""))
                # estado no se muestra en boleta
                if parts:
                    producto_info += f" ({' - '.join([p for p in parts if p])})"
                venta_local = (boleta.get("local") or "").strip()
                stock_local = (item.get("stock_local") or "").strip()
                stock_label = stock_local or venta_local
                if es_credito_personal:
                    rows.append(
                        [
                            str(item.get("cantidad", 0)),
                            producto_info,
                            stock_label,
                        ]
                    )
                else:
                    rows.append(
                        [
                            str(item.get("cantidad", 0)),
                            producto_info,
                            stock_label,
                            format_money(item.get("precio_unitario", 0)),
                            format_money(item.get("subtotal", 0)),
                        ]
                    )
            rows.append([""] * len(rows[0]))

            subtotal_productos = boleta.get("subtotal", 0)
            precio_envio = boleta.get("precio_envio", 0)
            descuento = boleta.get("descuento_monto", 0)
            total = boleta.get("total", 0)
            interes_monto = pago.get("tarjeta_interes_monto", 0) or 0
            interes_pct = pago.get("tarjeta_interes_pct", 0) or 0
            cuotas = pago.get("tarjeta_cuotas", 0) or 0
            if not es_credito_personal:
                rows.append(["", "", "Subtotal:", format_money(subtotal_productos), ""])
                if precio_envio > 0:
                    rows.append(["", "", "+ Envio:", format_money(precio_envio), ""])
                if descuento > 0:
                    rows.append(
                        ["", "", "- Descuento:", f"-{format_money(descuento)}", ""]
                    )
                if interes_monto > 0:
                    if interes_pct:
                        label = f"Interes tarjeta ({int(interes_pct)}%)"
                    else:
                        label = "Interes tarjeta"
                    rows.append(
                        ["", "", f"+ {label}:", format_money(interes_monto), ""]
                    )
                if "se?a" in tipo_pago or "sena" in tipo_pago:
                    rows.append([""] * len(rows[0]))
                    rows.append(["", "", "TOTAL:", format_money(total), ""])
                    rows.append(
                        [
                            "",
                            "",
                            "- Se?a:",
                            f"-{format_money(pago.get('monto_sena', 0))}",
                            "",
                        ]
                    )
                    rows.append(
                        [
                            "",
                            "",
                            "= RESTA:",
                            format_money(pago.get("monto_restante", 0)),
                            "",
                        ]
                    )
                else:
                    rows.append([""] * len(rows[0]))
                    rows.append(["", "", "TOTAL:", format_money(total), ""])

            if es_credito_personal:
                total_reserved = 35 + 90
                col_widths = [35, ancho_util - total_reserved, 90]
            else:
                total_reserved = 35 + 90 + 80 + 70
                col_widths = [35, ancho_util - total_reserved, 90, 80, 70]
            tabla = Table(rows, colWidths=col_widths)
            style = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("GRID", (0, 0), (-1, len(detalle)), 0.5, COLOR_BORDER),
                ("LINEBELOW", (0, len(detalle)), (-1, len(detalle)), 1, COLOR_BORDER),
            ]
            if not es_credito_personal:
                style.append(("ALIGN", (3, 1), (-1, -1), "RIGHT"))
                style.append(
                    ("FONTNAME", (2, len(detalle) + 2), (-1, -1), "Helvetica-Bold")
                )
                style.append(("FONTSIZE", (2, -1), (-1, -1), 10))
                if "se?a" in tipo_pago or "sena" in tipo_pago:
                    resta_row = len(rows) - 1
                    style.append(
                        ("BACKGROUND", (2, resta_row), (-1, resta_row), COLOR_WARNING)
                    )
                    style.append(
                        ("TEXTCOLOR", (2, resta_row), (-1, resta_row), colors.white)
                    )
            tabla.setStyle(TableStyle(style))

            try:
                tabla_height = tabla.wrapOn(c, ancho_util, page_h - 2 * margin)[1]
                tabla.drawOn(c, x_start, y_cursor - tabla_height - 5)
                y_cursor -= tabla_height + 15
            except Exception:
                c.setFont("Helvetica", 9)
                c.setFillColor(colors.red)
                c.drawString(
                    x_start,
                    y_cursor - 12,
                    "No fue posible renderizar el detalle completo por su longitud.",
                )
                c.setFillColor(colors.black)
                y_cursor -= 28

            # (Firmas y sucursales movidas al encabezado)

            # Firmas junto al logo (en pie)
            if not es_credito_personal:
                try:
                    sig_line_w = 120
                    sig_gap = 28
                    sig_y = margin + 25
                    sig_x2 = x_end - (float(PDF_LOGO_WIDTH_PT) + 20) - sig_line_w
                    sig_x1 = sig_x2 - sig_gap - sig_line_w
                    c.setStrokeColor(colors.black)
                    c.setLineWidth(1)
                    c.line(sig_x1, sig_y, sig_x1 + sig_line_w, sig_y)
                    c.line(sig_x2, sig_y, sig_x2 + sig_line_w, sig_y)
                    c.setFont("Helvetica", 8)
                    c.setFillColor(colors.black)
                    c.drawString(sig_x1, sig_y - 12, "Firma - Vendedor")
                    c.drawString(sig_x2, sig_y - 12, "Firma - Cliente")

                    # Datos del local a la izquierda de la firma del vendedor
                    local_dir, local_tel = _get_local_contact(boleta.get("local", ""))
                    info_x = sig_x1 - 200
                    c.setFont("Helvetica-Bold", 10)
                    if local_tel:
                        c.drawString(info_x, sig_y + 4, f"📞 {local_tel}")
                    if local_dir:
                        c.drawString(info_x, sig_y - 12, f"📍 {local_dir}")
                except Exception:
                    pass

        # ============ GENERACIÓN SEGÚN CANTIDAD DE ÍTEMS ============
        detalle_full = boleta.get("detalle", []) or []
        if len(detalle_full) <= 6:
            # Duplicado en una sola hoja (mitades)
            draw_mitad(
                page_h,
                es_copia_cliente=False,
                detalle_subset=detalle_full,
                show_totals=True,
            )
            draw_mitad(
                half_h,
                es_copia_cliente=True,
                detalle_subset=detalle_full,
                show_totals=True,
            )
            # Línea de corte punteada
            c.setStrokeColor(colors.grey)
            c.setLineWidth(0.5)
            c.setDash(3, 3)
            c.line(margin / 2, half_h, page_w - margin / 2, half_h)
            c.setFont("Helvetica", 7)
            c.setFillColor(colors.grey)
            c.drawString(page_w / 2 - 15, half_h - 3, "✂ Cortar aquí")
            c.showPage()
        else:
            # Dos hojas: Local (página 1), Cliente (página 2)
            draw_copia_full(es_copia_cliente=False, detalle_full=detalle_full)
            c.showPage()
            draw_copia_full(es_copia_cliente=True, detalle_full=detalle_full)
            c.showPage()

        # Finalizar PDF
        c.save()

        return True, out_path

    except Exception as e:
        import traceback

        error_detail = traceback.format_exc()
        return False, f"Error generando PDF: {str(e)}\n{error_detail}"
