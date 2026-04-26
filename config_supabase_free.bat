@echo off
REM Configuración para Supabase Free Tier (máx 60 conexiones)
REM Usar 10 conexiones por app permite hasta 5 mueblerías simultáneas

echo ========================================
echo CONFIGURACION SUPABASE FREE TIER
echo ========================================
echo.
echo Este script configura el pool de conexiones para Supabase Free.
echo.
echo Con 10 conexiones por app:
echo - 5 mueblerías = 50 conexiones totales
echo - Deja 10 conexiones libres en Supabase
echo.
echo ========================================

REM Establecer pool size a 10
set MANAREY_PG_POOL_MAX=10

echo.
echo ✓ Pool configurado a 10 conexiones
echo.
echo Iniciando aplicación...
echo.

REM Activar entorno virtual si existe
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Iniciar aplicación
python app.py

pause
