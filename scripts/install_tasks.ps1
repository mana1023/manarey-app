# install_tasks.ps1
# Script para ejecutar migraciones y asegurar usuarios en una nueva máquina.

Write-Host "Ejecutando migraciones y asegurando usuarios..."
$python = "python"
if (Test-Path .\.venv\Scripts\python.exe) { $python = .\.venv\Scripts\python.exe }

& $python .\scripts\run_migrations.py
& $python .\scripts\hash_passwords.py
& $python .\scripts\ensure_local_users.py

Write-Host "Listo. Arrancando aplicación..."
& $python .\app.py
