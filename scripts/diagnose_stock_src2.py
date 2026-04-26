import importlib
import inspect
import linecache
import sys
import traceback

# Clear linecache to avoid stale cached source
linecache.clearcache()

try:
    # Import fresh
    if "models.stock_model" in sys.modules:
        del sys.modules["models.stock_model"]
    m = importlib.import_module("models.stock_model")
    print("module_file:", getattr(m, "__file__", None))
    src = inspect.getsource(m)
    print("len(src)=", len(src))
    print("idx def get_queue_items =", src.find("def get_queue_items"))
    # Show direct read from disk for comparison
    with open(getattr(m, "__file__"), "r", encoding="utf-8") as fh:
        disk = fh.read()
    print("len(disk)=", len(disk))
    print("idx in disk=", disk.find("def get_queue_items"))
    print("--- disk slice at 320:420 lines ---")
    lines = disk.splitlines()
    for i in range(320, 440):
        print(i + 1, lines[i][:200] if i < len(lines) else "")
except Exception:
    traceback.print_exc()
