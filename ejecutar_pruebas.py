import subprocess
import sys

# Ejecutar script y capturar output
result = subprocess.run(
    [sys.executable, "prueba_stock_completa.py"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)

# Guardar en archivo
with open("resultado_pruebas_stock.txt", "w", encoding="utf-8") as f:
    f.write("STDOUT:\n")
    f.write(result.stdout)
    f.write("\n\nSTDERR:\n")
    f.write(result.stderr)
    f.write(f"\n\nExit code: {result.returncode}")

print("Test ejecutado. Resultados guardados en resultado_pruebas_stock.txt")
print(f"Exit code: {result.returncode}")
