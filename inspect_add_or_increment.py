import sys

sys.path.insert(0, ".")
import inspect

from models import stock_model as sm

print("function repr:", sm.add_or_increment)
try:
    print("signature:", inspect.signature(sm.add_or_increment))
except Exception as e:
    print("signature error:", e)
code = getattr(sm.add_or_increment, "__code__", None)
if code:
    print("code varnames:", code.co_varnames)
    print("argcount:", code.co_argcount)
    print("defaults:", sm.add_or_increment.__defaults__)
else:
    print("no code object")
