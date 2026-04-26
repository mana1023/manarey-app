"""
fix_constants.py — Repara las vistas que quedaron con constantes incompletas/rotas
tras patch_theme.py. Redefine TEXT, DARK, CARD, etc. como variables dinámicas que
se recalculan llamando a _T() en el momento de importar el módulo.
"""
import os
import re

VIEWS_DIR = r"c:\Users\USUARIO\Desktop\Manarey\views"

# Bloque de constantes dinámicas a insertar después del bloque try/except _T(...)
DYNAMIC_CONSTANTS = """
# ── Constantes de color dinámicas (se recalculan al arrancar) ────────────────
def _colors():
    return {
        "DORADO":      _T("GOLD",       "#C9A040"),
        "DARK":        _T("BG",         "#1f1f22"),
        "CARD":        _T("CARD",       "#232327"),
        "BORDER":      _T("BORDER",     "#34343a"),
        "TEXT":        _T("TEXT",       "#ECECF1"),
        "MUTED":       _T("TEXT_MUTED", "#c9c9cf"),
        "BG":          _T("BG",         "#0f0f14"),
        "BG_ALT":      _T("BG_ALT",     "#1a1a22"),
        "CARD_BG":     _T("CARD",       "#1a1a22"),
        "CARD_BORDER": _T("BORDER",     "rgba(201,160,64,0.18)"),
        "ACCENT":      _T("GOLD",       "#C9A040"),
        "TEXT_MUTED":  _T("TEXT_MUTED", "#a0a0a8"),
        "PRIMARY":     _T("GOLD",       "#C9A040"),
        "GREEN":       "#5E8B6F",
    }

_c = _colors()
DORADO      = _c["DORADO"]
DARK        = _c["DARK"]
CARD        = _c["CARD"]
BORDER      = _c["BORDER"]
TEXT        = _c["TEXT"]
MUTED       = _c["MUTED"]
BG          = _c["BG"]
BG_ALT      = _c["BG_ALT"]
CARD_BG     = _c["CARD_BG"]
CARD_BORDER = _c["CARD_BORDER"]
ACCENT      = _c["ACCENT"]
TEXT_MUTED  = _c["TEXT_MUTED"]
PRIMARY     = _c["PRIMARY"]
# ─────────────────────────────────────────────────────────────────────────────
"""

INJECTION_MARKER = "    def _T(k, fallback): return fallback"


def fix_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Only process files that have the _T helper
    if "_T(k, fallback)" not in content:
        return False

    # Skip if already patched
    if "_colors()" in content:
        print(f"  already patched: {os.path.basename(path)}")
        return False

    # 1. Remove any leftover broken/partial constant lines like "TEXT_\n" or "HEAD_\n"
    #    These are lines that start with a known constant name followed by _, meaning they were cut.
    content = re.sub(
        r"^(TEXT|HEAD|GRID|ERROR|BG|CARD|BADGE|PENDING|DARK|ACCENT|MUTED|BORDER)_\s*$",
        "",
        content,
        flags=re.MULTILINE,
    )

    # 2. Remove empty definitions like "DARK = " (no value after =), which are broken
    content = re.sub(r"^[A-Z_]+ = \s*$", "", content, flags=re.MULTILINE)

    # 3. Remove leftover duplicate constant definitions for things we're going to redefine.
    #    Only remove if they were left as standalone empty-ish lines (already partially removed by patch_theme).
    constants_to_redefine = [
        "DORADO",
        "DARK",
        "CARD",
        "BORDER",
        "TEXT",
        "MUTED",
        "BG",
        "BG_ALT",
        "CARD_BG",
        "CARD_BORDER",
        "ACCENT",
        "TEXT_MUTED",
    ]
    for c in constants_to_redefine:
        # Remove lines like: `CONSTNAME = "..."`
        content = re.sub(rf'^{c} = "[^"]*"\s*$', "", content, flags=re.MULTILINE)

    # 4. Inject dynamic constants after the _T fallback line
    if INJECTION_MARKER in content:
        content = content.replace(
            INJECTION_MARKER, INJECTION_MARKER + "\n" + DYNAMIC_CONSTANTS
        )

    # Clean up triple blank lines
    content = re.sub(r"\n{4,}", "\n\n\n", content)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


for fname in os.listdir(VIEWS_DIR):
    if not fname.endswith(".py"):
        continue
    path = os.path.join(VIEWS_DIR, fname)
    try:
        changed = fix_file(path)
        if changed:
            print(f"Fixed: {fname}")
    except Exception as e:
        print(f"ERROR {fname}: {e}")

print("Done.")
