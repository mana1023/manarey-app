import importlib
import inspect
import sys

if "models.stock_model" in sys.modules:
    del sys.modules["models.stock_model"]
m = importlib.import_module("models.stock_model")
src = inspect.getsource(m)
print("len src=", len(src))
print("--- tail ---")
print(src[-800:])
