import importlib
import inspect

m = importlib.import_module("models.stock_model")
src = inspect.getsource(m)
print("len source", len(src))
print("has def get_queue_items in source?", "def get_queue_items" in src)
# print first 800 chars
print(src[:800])
