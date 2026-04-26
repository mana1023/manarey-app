@echo off
setlocal
set SCRIPT_DIR=%~dp0
set PS1=%SCRIPT_DIR%actualizacion.ps1

if not exist "%PS1%" (
  echo No se encontro actualizacion.ps1
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
endlocal
