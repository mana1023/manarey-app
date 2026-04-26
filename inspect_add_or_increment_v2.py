import sys

sys.path.insert(0, ".")
from models import stock_model as sm

print("add_or_increment is", sm.add_or_increment)
print("add_or_increment firstlineno", sm.add_or_increment.__code__.co_firstlineno)
print("has add_or_increment_v2?", hasattr(sm, "add_or_increment_v2"))
if hasattr(sm, "add_or_increment_v2"):
    print("v2 firstlineno", sm.add_or_increment_v2.__code__.co_firstlineno)
print(
    "globals replace check:",
    sm.__dict__.get("add_or_increment") is sm.__dict__.get("add_or_increment_v2"),
)
