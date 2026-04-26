import traceback

p = r"c:\\Users\\USUARIO\\Desktop\\Manarey\\models\\stock_model.py"
src = open(p, "r", encoding="utf-8").read()
ns = {}
try:
    exec(src, ns)
    print("exec completed")
except Exception:
    print("exec raised:")
    traceback.print_exc()
print(
    "defined names sample:",
    [k for k in ns.keys() if "queue" in k.lower() or "enqueue" in k.lower()][:20],
)
