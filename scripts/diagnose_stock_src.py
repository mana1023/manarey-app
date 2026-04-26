import importlib
import inspect
import traceback

try:
    m = importlib.import_module("models.stock_model")
    print("module_file:", getattr(m, "__file__", None))
    src = inspect.getsource(m)
    print("len(src)=", len(src))
    print("idx def get_queue_items =", src.find("def get_queue_items"))
    # print a small head/mid repr
    print("head repr:", repr(src[:1000]))
    print("mid repr:", repr(src[20000:20200]))
except Exception:
    traceback.print_exc()
