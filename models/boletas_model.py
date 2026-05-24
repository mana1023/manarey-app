# models/boletas_model.py - PDF MEJORADO VERSIÓN FINAL
import json
import os
from decimal import ROUND_HALF_UP, Decimal  # noqa: F401

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

from config import PDF_LOGO_Y_OFFSET  # noqa: F401
from config import (
    PDF_LOGO_FALLBACK,
    PDF_LOGO_POSITION,
    PDF_LOGO_PRIMARY,
    PDF_LOGO_WIDTH_PT,
)
from models import db as db_mod


def format_money(value):
    """Formatea valores monetarios"""
    from utils.money import format_money_es

    try:
        return format_money_es(value)
    except Exception:
        return f"${value}"


def _is_sena(tipo_pago: str) -> bool:
    t = (tipo_pago or "").lower()
    return ("sena" in t) or ("seña" in t) or ("se?a" in t)


def _credito_personal_tiene_entrega(pago: dict) -> bool:
    try:
        return float(pago.get("monto_sena") or 0) > 0.01
    except Exception:
        return False


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


def _get_completion_info(boleta: dict) -> dict:
    info = boleta.get("completacion") or {}
    return info if isinstance(info, dict) else {}


def _shipping_charged_at_domicile(boleta: dict) -> bool:
    try:
        incluye_envio = int(boleta.get("incluye_envio") or 0)
    except Exception:
        incluye_envio = 0
    try:
        precio_envio = float(boleta.get("precio_envio") or 0)
    except Exception:
        precio_envio = 0.0
    forma_envio = str(boleta.get("forma_pago_envio") or "").strip().lower()
    return (
        incluye_envio == 1
        and precio_envio > 0
        and forma_envio in ("domicilio", "en domicilio")
    )


def _get_printable_total(boleta: dict) -> float:
    try:
        total = float(boleta.get("total") or 0)
    except Exception:
        total = 0.0
    if not _shipping_charged_at_domicile(boleta):
        return total
    try:
        subtotal = float(boleta.get("subtotal") or 0)
    except Exception:
        subtotal = 0.0
    try:
        descuento = float(boleta.get("descuento_monto") or 0)
    except Exception:
        descuento = 0.0
    pago = boleta.get("pago") or {}
    try:
        interes = float(pago.get("tarjeta_interes_monto") or 0)
    except Exception:
        interes = 0.0
    total_sin_envio = max(0.0, subtotal - descuento + interes)
    if abs(total - total_sin_envio) <= 0.01:
        return total
    try:
        precio_envio = float(boleta.get("precio_envio") or 0)
    except Exception:
        precio_envio = 0.0
    return max(0.0, total - precio_envio)


def _is_paid_at_domicile(pago: dict) -> bool:
    tipo_pago = str(pago.get("tipo_abono") or "").strip().lower()
    if "domicilio" in tipo_pago:
        return True
    forma_pago = str(pago.get("forma_pago") or "").strip().lower()
    if "domicilio" in forma_pago:
        return True
    for item in pago.get("formas") or []:
        try:
            forma = str(item.get("forma") or "").strip().lower()
        except Exception:
            forma = ""
        if "domicilio" in forma:
            return True
    return False


def _get_display_payment_breakdown(boleta: dict, pago: dict) -> str:
    formas_list = pago.get("formas") or []
    if not formas_list:
        return ""

    normalized = []
    try:
        for item in formas_list:
            if isinstance(item, dict):
                forma = str(item.get("forma") or "").strip()
                monto = float(item.get("monto") or 0)
            else:
                forma = str(item[0] or "").strip()
                monto = float(item[1] or 0)
            normalized.append({"forma": forma, "monto": monto})
    except Exception:
        normalized = []

    if not normalized:
        return ""

    try:
        printable_total = float(_get_printable_total(boleta) or 0)
    except Exception:
        printable_total = 0.0
    current_total = sum(float(it.get("monto") or 0) for it in normalized)
    excess = max(0.0, current_total - printable_total)

    if excess > 0.009:
        adjusted = [dict(it) for it in normalized]
        candidate_indexes = [
            idx
            for idx, it in enumerate(adjusted)
            if "domicilio" not in str(it.get("forma") or "").strip().lower()
        ]
        if not candidate_indexes:
            candidate_indexes = list(range(len(adjusted)))
        for idx in candidate_indexes:
            if excess <= 0.009:
                break
            monto_actual = float(adjusted[idx].get("monto") or 0)
            descuento = min(monto_actual, excess)
            adjusted[idx]["monto"] = max(0.0, monto_actual - descuento)
            excess -= descuento
        normalized = adjusted

    return " | ".join(
        [
            f"{str(it.get('forma') or '')}: {format_money(it.get('monto') or 0)}"
            for it in normalized[:3]
        ]
    )


def _build_payment_box_info(
    boleta: dict, pago: dict, color_success, color_warning, color_info, color_dorado
):
    tipo_pago = (pago.get("tipo_abono") or "").lower()
    completion = _get_completion_info(boleta)
    printable_total = _get_printable_total(boleta)
    if completion:
        completion_type = (completion.get("tipo") or "").strip().lower()
        amount = completion.get("monto", 0) or 0
        original_date = _fmt_datetime(completion.get("fecha_original", ""))
        forma = completion.get("forma_pago") or pago.get("forma_pago") or "N/A"
        if completion_type == "domicilio":
            return {
                "color": color_info,
                "estado": "SE COMPLETO EL PAGO EN DOMICILIO",
                "detalle1": "Monto cobrado:",
                "detalle2": f"{format_money(amount)}",
                "detalle3": f"Venta original: {original_date}",
                "detalle4": f"Metodo: {forma}",
            }
        return {
            "color": color_warning,
            "estado": "SE PAGO EL RESTO DE LA SEÑA",
            "detalle1": "Monto abonado:",
            "detalle2": f"{format_money(amount)}",
            "detalle3": f"Venta original: {original_date}",
            "detalle4": f"Metodo: {forma}",
        }
    es_credito_personal = "credito_personal" in tipo_pago
    if es_credito_personal:
        entrega_inicial = pago.get("monto_sena", 0) or 0
        saldo_credito = pago.get("monto_restante", 0) or 0
        return {
            "color": color_dorado,
            "estado": "CREDITO PERSONAL",
            "detalle1": f"Entrega: {format_money(entrega_inicial)}",
            "detalle2": f"Saldo: {format_money(saldo_credito)}",
            "detalle3": "",
            "detalle4": "",
        }
    if _is_sena(tipo_pago):
        monto_sena = pago.get("monto_sena", 0)
        monto_restante = pago.get("monto_restante", 0)
        return {
            "color": color_warning,
            "estado": "SEÑA PAGADA",
            "detalle1": f"Seña: {format_money(monto_sena)}",
            "detalle2": f"Resta: {format_money(monto_restante)}",
            "detalle3": "",
            "detalle4": "",
        }
    if _is_paid_at_domicile(pago):
        return {
            "color": color_info,
            "estado": "PAGO COMPLETO EN DOMICILIO",
            "detalle1": "Monto del pedido:",
            "detalle2": f"{format_money(printable_total)}",
            "detalle3": "",
            "detalle4": "",
        }
    return {
        "color": color_success,
        "estado": "PAGO COMPLETO",
        "detalle1": "Total pagado:",
        "detalle2": f"{format_money(printable_total)}",
        "detalle3": "",
        "detalle4": "",
    }


def _draw_footer_local_info(
    c, boleta: dict, x_start: float, x_end: float, y_bottom: float, logo_path: str
):
    local_dir, local_tel = _get_local_contact(boleta.get("local", ""))
    text_x = x_start
    text_y = y_bottom + 44

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    text_lines = []
    if local_tel:
        text_lines.append(f"Telefono: {local_tel}")
    if local_dir:
        text_lines.append(f"Direccion: {local_dir}")

    max_text_width = 0
    for idx, line in enumerate(text_lines):
        y = text_y - (14 * idx)
        c.drawString(text_x, y, line)
        try:
            max_text_width = max(
                max_text_width, c.stringWidth(line, "Helvetica-Bold", 9)
            )
        except Exception:
            pass


def _draw_footer_logo_background(
    c, x_start: float, x_end: float, y_bottom: float, logo_path: str
):
    if not logo_path or PDF_LOGO_POSITION != "footer-right":
        return
    try:
        img = ImageReader(logo_path)
        iw, ih = img.getSize()
        target_w = min(float(PDF_LOGO_WIDTH_PT), 460.0)
        aspect = ih / float(iw) if iw else 0.24
        target_h = max(30.0, target_w * aspect)
        max_footer_height = 220.0
        if target_h > max_footer_height and target_h > 0:
            scale = max_footer_height / target_h
            target_h = max_footer_height
            target_w = target_w * scale
        available_w = max(0.0, x_end - x_start - target_w)
        x_logo = x_start + max(0.0, available_w * 0.28)
        y_logo = y_bottom - 28
        c.saveState()
        try:
            c.setFillAlpha(0.58)
        except Exception:
            pass
        c.drawImage(
            img,
            x_logo,
            y_logo,
            width=target_w,
            height=target_h,
            preserveAspectRatio=True,
            mask="auto",
        )
        c.restoreState()
    except Exception:
        pass


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
            title_prefix = (
                "COMPROBANTE DE COMPLETACION"
                if _get_completion_info(boleta)
                else "BOLETA Nº"
            )
            c.drawString(
                x_start + title_x_offset,
                y_top - 20,
                f"{title_prefix} {boleta.get('numero_boleta', 'N/A')}",
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

            # Agregar entre calles si existe (envío o retiro)
            if cliente.get("entre_calles"):
                entre_calles = cliente.get("entre_calles")
                partes_direccion.append(f"(entre {entre_calles})")

            y_offset = -20
            if partes_direccion:
                direccion = ", ".join(partes_direccion)
                # Dividir dirección si es muy larga
                if len(direccion) > 50:
                    c.drawString(x_start + 5, y_cliente - 20, f"• {direccion[:50]}")
                    c.drawString(x_start + 5, y_cliente - 30, f"  {direccion[50:]}")
                    y_offset = -40
                else:
                    c.drawString(x_start + 5, y_cliente - 20, f"• {direccion}")

            # Notas del domicilio / descripción
            notas_boleta = (boleta.get("notas") or "").strip()
            if notas_boleta:
                c.drawString(
                    x_start + 5, y_cliente + y_offset - 10, f"• Notas: {notas_boleta}"
                )
                y_cursor -= 72
            else:
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
            pago_box = _build_payment_box_info(
                boleta, pago, COLOR_SUCCESS, COLOR_WARNING, COLOR_INFO, COLOR_DORADO
            )
            color_pago = pago_box["color"]
            estado_texto = pago_box["estado"]
            detalle_pago = pago_box["detalle1"]
            detalle_pago2 = pago_box["detalle2"]
            detalle_pago3 = ""
            if es_credito_personal:
                if _credito_personal_tiene_entrega(pago):
                    detalle_pago = "Pago inicial:"
                    detalle_pago2 = f"{format_money(pago.get('monto_sena', 0) or 0)}"
                    detalle_pago3 = f"Saldo financiado: {format_money(pago.get('monto_restante', 0) or 0)}"
                else:
                    detalle_pago = "Operacion financiada"
                    detalle_pago2 = ""
                    detalle_pago3 = "Sin importes en esta copia"
            detalle_pago3 = ""
            if es_credito_personal:
                if _credito_personal_tiene_entrega(pago):
                    detalle_pago = "Pago inicial:"
                    detalle_pago2 = f"{format_money(pago.get('monto_sena', 0) or 0)}"
                    detalle_pago3 = f"Saldo financiado: {format_money(pago.get('monto_restante', 0) or 0)}"
                else:
                    detalle_pago = "Operacion financiada"
                    detalle_pago2 = ""
                    detalle_pago3 = "Sin importes en esta copia"

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
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.black)
            c.drawString(box_pago_x + 8, y_cursor + 40, detalle_pago)
            if detalle_pago2:
                c.setFont("Helvetica-Bold", 9)
                c.drawString(box_pago_x + 8, y_cursor + 30, detalle_pago2)

            # Forma(s) de pago
            c.setFont("Helvetica", 8)
            formas_list = pago.get("formas") or []
            if _get_completion_info(boleta):
                c.drawString(
                    box_pago_x + 8, y_cursor + 18, pago_box.get("detalle3", "")
                )
                c.drawString(box_pago_x + 8, y_cursor + 8, pago_box.get("detalle4", ""))
            elif es_credito_personal:
                c.drawString(box_pago_x + 8, y_cursor + 18, detalle_pago3)
            elif formas_list:
                breakdown = _get_display_payment_breakdown(boleta, pago)
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
            incluye_envio = int(
                boleta.get("incluye_envio") or (1 if precio_envio else 0)
            )
            forma_envio = str(boleta.get("forma_pago_envio") or "").strip().lower()
            descuento = boleta.get("descuento_monto", 0)
            total = _get_printable_total(boleta)
            interes_monto = pago.get("tarjeta_interes_monto", 0) or 0
            interes_pct = pago.get("tarjeta_interes_pct", 0) or 0
            cuotas = pago.get("tarjeta_cuotas", 0) or 0

            if show_totals and not es_credito_personal:
                # Subtotal productos
                rows.append(["", "", "Subtotal:", format_money(subtotal_productos), ""])
                # Envio: si se cobra en domicilio se informa, pero no suma al total impreso.
                if incluye_envio == 1:
                    if forma_envio in ("local", "en local"):
                        rows.append(
                            ["", "", "+ Envio:", format_money(precio_envio), ""]
                        )
                        rows.append(["", "", "Pago envio:", "Pagado en local", ""])
                    elif forma_envio in ("domicilio", "en domicilio"):
                        rows.append(["", "", "Envio:", format_money(precio_envio), ""])
                        rows.append(
                            ["", "", "Pago envio:", "Se cobra en domicilio", ""]
                        )
                    else:
                        rows.append(
                            ["", "", "+ Envio:", format_money(precio_envio), ""]
                        )
                        rows.append(["", "", "Pago envio:", "Sin dato", ""])
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
                completion = _get_completion_info(boleta)
                if completion:
                    rows.append([""] * len(rows[0]))
                    rows.append(["", "", "TOTAL VENTA:", format_money(total), ""])
                    if (completion.get("tipo") or "").strip().lower() == "domicilio":
                        rows.append(
                            [
                                "",
                                "",
                                "Monto cobrado hoy:",
                                format_money(completion.get("monto", 0)),
                                "",
                            ]
                        )
                    else:
                        rows.append(
                            [
                                "",
                                "",
                                "Monto abonado hoy:",
                                format_money(completion.get("monto", 0)),
                                "",
                            ]
                        )
                    rows.append(
                        [
                            "",
                            "",
                            "Venta original:",
                            _fmt_date_only(completion.get("fecha_original", "")),
                            "",
                        ]
                    )
                    rows.append(
                        [
                            "",
                            "",
                            "Metodo:",
                            str(completion.get("forma_pago", "") or "Sin dato"),
                            "",
                        ]
                    )
                # Si hay seña, mostrar desglose
                elif _is_sena(tipo_pago):
                    monto_sena = pago.get("monto_sena", 0)
                    monto_restante = pago.get("monto_restante", 0)
                    rows.append([""] * len(rows[0]))
                    rows.append(["", "", "TOTAL:", format_money(total), ""])
                    rows.append(["", "", "- Seña:", f"-{format_money(monto_sena)}", ""])
                    rows.append(["", "", "= RESTA:", format_money(monto_restante), ""])
                else:
                    rows.append([""] * len(rows[0]))
                    rows.append(["", "", "TOTAL:", format_money(total), ""])

            footer_y = y_base - half_h + 5
            _draw_footer_logo_background(c, x_start, x_end, footer_y, logo_path)

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
                # Si hay seña, destacar la línea RESTA
                if _is_sena(tipo_pago) and not _get_completion_info(boleta):
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

            footer_y = y_base - half_h + 5
            _draw_footer_local_info(c, boleta, x_start, x_end, footer_y, logo_path)

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
                    title_x_offset = int(target_w) + 30
                except:
                    pass

            # Número de boleta
            c.setFont("Helvetica-Bold", 14)
            c.setFillColor(COLOR_DORADO)
            title_prefix = (
                "COMPROBANTE DE COMPLETACION"
                if _get_completion_info(boleta)
                else "BOLETA Nº"
            )
            c.drawString(
                x_start + title_x_offset,
                y_top - 20,
                f"{title_prefix} {boleta.get('numero_boleta', 'N/A')}",
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
            if cliente.get("entre_calles"):
                partes_direccion.append(f"(entre {cliente.get('entre_calles')})")
            y_offset2 = -20
            if partes_direccion:
                direccion = ", ".join(partes_direccion)
                if len(direccion) > 70:
                    c.drawString(x_start + 5, y_cliente - 20, f"• {direccion[:70]}")
                    c.drawString(x_start + 5, y_cliente - 30, f"  {direccion[70:]}")
                    y_offset2 = -40
                else:
                    c.drawString(x_start + 5, y_cliente - 20, f"• {direccion}")

            notas_boleta2 = (boleta.get("notas") or "").strip()
            if notas_boleta2:
                c.drawString(
                    x_start + 5, y_cliente + y_offset2 - 10, f"• Notas: {notas_boleta2}"
                )
                y_cursor -= 72
            else:
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
            pago_box = _build_payment_box_info(
                boleta, pago, COLOR_SUCCESS, COLOR_WARNING, COLOR_INFO, COLOR_DORADO
            )
            color_pago = pago_box["color"]
            estado_texto = pago_box["estado"]
            detalle_pago = pago_box["detalle1"]
            detalle_pago2 = pago_box["detalle2"]
            detalle_pago3 = pago_box.get("detalle3", "")

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
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.black)
            c.drawString(box_pago_x + 8, y_cursor + 40, detalle_pago)
            if detalle_pago2:
                c.setFont("Helvetica-Bold", 9)
                c.drawString(box_pago_x + 8, y_cursor + 30, detalle_pago2)
            c.setFont("Helvetica", 8)
            formas_list = pago.get("formas") or []
            if _get_completion_info(boleta):
                c.drawString(box_pago_x + 8, y_cursor + 18, detalle_pago3)
                c.drawString(box_pago_x + 8, y_cursor + 8, pago_box.get("detalle4", ""))
            elif es_credito_personal:
                c.drawString(box_pago_x + 8, y_cursor + 18, detalle_pago3)
            elif formas_list:
                breakdown = _get_display_payment_breakdown(boleta, pago)
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
            incluye_envio = int(
                boleta.get("incluye_envio") or (1 if precio_envio else 0)
            )
            forma_envio = str(boleta.get("forma_pago_envio") or "").strip().lower()
            descuento = boleta.get("descuento_monto", 0)
            total = _get_printable_total(boleta)
            interes_monto = pago.get("tarjeta_interes_monto", 0) or 0
            interes_pct = pago.get("tarjeta_interes_pct", 0) or 0
            cuotas = pago.get("tarjeta_cuotas", 0) or 0
            if not es_credito_personal:
                rows.append(["", "", "Subtotal:", format_money(subtotal_productos), ""])
                if incluye_envio == 1:
                    if forma_envio in ("local", "en local"):
                        rows.append(
                            ["", "", "+ Envio:", format_money(precio_envio), ""]
                        )
                        rows.append(["", "", "Pago envio:", "Pagado en local", ""])
                    elif forma_envio in ("domicilio", "en domicilio"):
                        rows.append(["", "", "Envio:", format_money(precio_envio), ""])
                        rows.append(
                            ["", "", "Pago envio:", "Se cobra en domicilio", ""]
                        )
                    else:
                        rows.append(
                            ["", "", "+ Envio:", format_money(precio_envio), ""]
                        )
                        rows.append(["", "", "Pago envio:", "Sin dato", ""])
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
                completion = _get_completion_info(boleta)
                if completion:
                    rows.append([""] * len(rows[0]))
                    rows.append(["", "", "TOTAL VENTA:", format_money(total), ""])
                    if (completion.get("tipo") or "").strip().lower() == "domicilio":
                        rows.append(
                            [
                                "",
                                "",
                                "Monto cobrado hoy:",
                                format_money(completion.get("monto", 0)),
                                "",
                            ]
                        )
                    else:
                        rows.append(
                            [
                                "",
                                "",
                                "Monto abonado hoy:",
                                format_money(completion.get("monto", 0)),
                                "",
                            ]
                        )
                    rows.append(
                        [
                            "",
                            "",
                            "Venta original:",
                            _fmt_date_only(completion.get("fecha_original", "")),
                            "",
                        ]
                    )
                    rows.append(
                        [
                            "",
                            "",
                            "Metodo:",
                            str(completion.get("forma_pago", "") or "Sin dato"),
                            "",
                        ]
                    )
                elif _is_sena(tipo_pago):
                    rows.append([""] * len(rows[0]))
                    rows.append(["", "", "TOTAL:", format_money(total), ""])
                    rows.append(
                        [
                            "",
                            "",
                            "- Seña:",
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
            elif (
                show_totals  # noqa: F821
                and es_credito_personal
                and _credito_personal_tiene_entrega(pago)
            ):
                entrega_inicial = pago.get("monto_sena", 0) or 0
                saldo_credito = pago.get("monto_restante", 0) or 0
                rows.append([""] * len(rows[0]))
                rows.append(["", "", "TOTAL:", format_money(total)])
                rows.append(
                    ["", "", "- Entrega inicial:", format_money(entrega_inicial)]
                )
                rows.append(
                    ["", "", "= Saldo credito personal:", format_money(saldo_credito)]
                )

            footer_y = margin + 5
            _draw_footer_logo_background(c, x_start, x_end, footer_y, logo_path)

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
                if _is_sena(tipo_pago) and not _get_completion_info(boleta):
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

            footer_y = margin + 5
            _draw_footer_local_info(c, boleta, x_start, x_end, footer_y, logo_path)

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
