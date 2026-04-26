import tempfile
from pathlib import Path


def save_receipt_stub(html_text: str, filename: str):
    """Guarda un stub de boleta HTML en una carpeta temporal (no persiste en el proyecto)."""
    temp_dir = Path(tempfile.mkdtemp(prefix="manarey_boleta_html_"))
    out = temp_dir / f"{filename}.html"
    out.write_text(html_text, encoding="utf-8")
    return str(out)
