import os
import re

views_dir = r"c:\Users\USUARIO\Desktop\Manarey\views"

# Patterns to match the hardcoded colors:
# DORADO = "#C9A040"
# DARK = "#1f1f22"
# etc.

# We will wrap the class init method or inject a _refresh_colors function.
# Actually, the simplest way is to replace `DARK` in `f"something {DARK}"` with `_T('BG')`
# But python f-strings are parsed. We can just replace the variable definitions with:
injection = """
try:
    import app_theme as _theme
    def _T(k, fallback): return _theme.get_palette_value(k) or fallback
except ImportError:
    def _T(k, fallback): return fallback

"""

for root, _, files in os.walk(views_dir):
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        with open(path, "r", encoding="utf-8") as file:
            content = file.read()

        modified = False

        # Replace constants with property-like lambda or getter calls
        # Since they are just used globally at instantiation time, we can replace the constants with dynamic calls if we just make them dynamic!
        # But wait, python evaluates default kwargs once.
        # Actually, if we just define them as properties or calls?
        # The easiest is: `def DARK(): return _T('BG', '#1f1f22')` and then change `{DARK}` to `{DARK()}`.
        # Let's just do a regex replace so `{DARK}` becomes `{_T('BG', '#1f1f22')}`

        replacements = [
            (r'DORADO = ".*?"', ""),
            (r'DARK = ".*?"', ""),
            (r'CARD = ".*?"', ""),
            (r'BORDER = ".*?"', ""),
            (r'TEXT = ".*?"', ""),
            (r'MUTED = ".*?"', ""),
            (r'BG = ".*?"', ""),
            (r'CARD_BG = ".*?"', ""),
            (r'CARD_BORDER = ".*?"', ""),
            (r'ACCENT = ".*?"', ""),
            (r'TEXT_MUTED = ".*?"', ""),
            (r"\{DORADO\}", r"""{_T('GOLD', '#C9A040')}"""),
            (r"\{DARK\}", r"""{_T('BG', '#1f1f22')}"""),
            (r"\{CARD\}", r"""{_T('CARD', '#232327')}"""),
            (r"\{BORDER\}", r"""{_T('BORDER', '#34343a')}"""),
            (r"\{TEXT\}", r"""{_T('TEXT', '#ECECF1')}"""),
            (r"\{MUTED\}", r"""{_T('TEXT_MUTED', '#c9c9cf')}"""),
            (r"\{BG\}", r"""{_T('BG', '#0f0f14')}"""),
            (r"\{CARD_BG\}", r"""{_T('CARD', '#1a1a22')}"""),
            (r"\{CARD_BORDER\}", r"""{_T('BORDER', 'rgba(201,160,64,0.18)')}"""),
            (r"\{ACCENT\}", r"""{_T('GOLD', '#C9A040')}"""),
            (r"\{TEXT_MUTED\}", r"""{_T('TEXT_MUTED', '#a0a0a8')}"""),
        ]

        if "DARK =" in content or "BG =" in content:
            for pat, rep in replacements:
                content = re.sub(pat, rep, content)

            # import injection after standard imports
            content = content.replace(
                "from PyQt5.QtWidgets import (",
                injection + "from PyQt5.QtWidgets import (",
            )

            with open(path, "w", encoding="utf-8") as file:
                file.write(content)
            print(f"Patched {f}")
