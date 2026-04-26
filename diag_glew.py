import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

print("=== Test Glew ===")
try:
    from models.stock_model import _row_to_dict, get_stock_filtered, list_by_local

    rows = list_by_local("Glew", "", "", "", "", "", "", "")
    print(f"list_by_local('Glew'): {len(rows)} filas")
    if rows:
        print("Primer row:", rows[0])
        d = _row_to_dict(rows[0])
        print("Primer dict:", d)
    else:
        print("Sin filas!")

    rows2 = get_stock_filtered("Glew", apply_reservas=False)
    print(f"get_stock_filtered('Glew'): {len(rows2)} dicts")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback

    traceback.print_exc()
print("=== Fin ===")
