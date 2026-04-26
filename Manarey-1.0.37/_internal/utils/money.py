from decimal import ROUND_HALF_UP, Decimal


def format_money_es(value) -> str:
    """Formatea dinero al estilo ES: $1.234,56 (maneja None y strings)."""
    try:
        d = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        s = f"{d:,.2f}"  # 1,234.56
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234,56
        return f"${s}"
    except Exception:
        try:
            return f"${float(value):.2f}"  # fallback
        except Exception:
            return f"${value}"
