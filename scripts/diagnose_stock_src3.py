import importlib
import inspect
import linecache
import sys
import traceback

linecache.clearcache()
try:
    if "models.stock_model" in sys.modules:
        del sys.modules["models.stock_model"]
    m = importlib.import_module("models.stock_model")
    print("module_file:", getattr(m, "__file__", None))
    src = inspect.getsource(m)
    print("len(src)=", len(src))
    print("idx def get_queue_items =", src.find("def get_queue_items"))
    print("idx get_queue_items =", src.find("get_queue_items"))
    with open(getattr(m, "__file__"), "r", encoding="utf-8") as fh:
        disk = fh.read()
    print("len(disk)=", len(disk))
    print("idx in disk def get_queue_items =", disk.find("def get_queue_items"))
    print("idx in disk get_queue_items =", disk.find("get_queue_items"))
    if disk.find("get_queue_items") != -1:
        i = disk.find("get_queue_items")
        print("context around disk match:", repr(disk[max(0, i - 80) : i + 80]))
    else:
        print("no disk match for get_queue_items")
except Exception:
    traceback.print_exc()
