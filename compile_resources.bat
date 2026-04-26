@echo off
setlocal

REM Verificar si pyrcc5 está en el PATH
where pyrcc5 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: No se encontró pyrcc5 en el PATH.
    echo Asegúrate de tener PyQt5 instalado y en el PATH.
    pause
    exit /b 1
)

echo Compilando recursos...
pyrcc5 -o resources_rc.py resources.qrc

if %ERRORLEVEL% EQU 0 (
    echo Recursos compilados exitosamente a resources_rc.py
) else (
    echo Error al compilar los recursos.
    pause
    exit /b 1
)

pause
