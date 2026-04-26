import importlib
import sys
import traceback

try:
    if "models.stock_model" in sys.modules:
        del sys.modules["models.stock_model"]
    m = importlib.import_module("models.stock_model")
    print("module_file:", getattr(m, "__file__", None))
    names = [
        n
        for n in dir(m)
        if "queue" in n
        or "enqueue" in n
        or n.startswith("get_queue")
        or n in ("enqueue_op", "get_queue_items")
    ]
    print("queue_symbols:", names)
    print("has get_queue_items attr?", hasattr(m, "get_queue_items"))
    print("has enqueue_op attr?", hasattr(m, "enqueue_op"))
except Exception:
    traceback.print_exc()
