from PIL import Image

SRC = r"assets/images/logo_manarey.png"
DST = r"assets/images/logo_manarey.ico"

img = Image.open(SRC)
# Sugeridos para Windows (incluye 256 para alta resolución)
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save(DST, sizes=sizes)
print(f"Creado: {DST}")
