import os
import sys

SCRIPT_DIR = os.path.dirname(__file__)
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models import ventas_model as vm

cliente_data = {
    "nombre": "Cliente Test",
    "telefono": "",
    "calle": "",
    "numero": "",
    "localidad": "",
}
items = [
    {
        "producto_id": 1,
        "cantidad": 1,
        "precio_unitario": 100.0,
        "nombre": "ProdTest",
        "categoria": "",
        "medida": "",
        "estado": "",
    }
]

ok, msg, vid = vm.registrar_venta("TEST_LOCAL", "tester", cliente_data, items, None, 0)
print("ok=", ok, "msg=", msg, "venta_id=", vid)
