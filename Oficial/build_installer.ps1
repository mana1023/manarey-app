<#
Build script para generar un ejecutable de Manarey con PyInstaller.
Requisitos previos: Python 3.11+, pip y acceso a internet para instalar dependencias.
Uso:
  - En PowerShell, desde la raíz del proyecto:  .\Oficial\build_installer.ps1
  - Para limpiar y reconstruir todo:          .\Oficial\build_installer.ps1 -Clean
#>
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$root   = Split-Path -Parent $PSScriptRoot
$venv   = Join-Path $PSScriptRoot ".venv_inst"
$python = Join-Path $venv "Scripts\python.exe"
$pyinst = Join-Path $venv "Scripts\pyinstaller.exe"

# Cerrar Manarey si está abierto para evitar archivos bloqueados
try {
    Get-Process -Name "Manarey" -ErrorAction SilentlyContinue | Stop-Process -Force
} catch {
    # no-op
}

function Remove-PathSafe($path) {
    if (-not (Test-Path $path)) { return }
    for ($i = 0; $i -lt 5; $i++) {
        try {
            Remove-Item $path -Recurse -Force -ErrorAction Stop
            return
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    Write-Warning "No se pudo limpiar $path (archivo en uso). Cierra Manarey/Explorer y reintenta."
}

# Limpiar salidas viejas para evitar que el instalador agarre el onefile anterior
$distOneFile = Join-Path $root "dist\Manarey.exe"
$distOneDir  = Join-Path $root "dist\Manarey"
if (Test-Path $distOneFile) { Remove-PathSafe $distOneFile }
if (Test-Path $distOneDir)  { Remove-PathSafe $distOneDir }

if ($Clean -and (Test-Path $venv)) {
    Remove-Item $venv -Recurse -Force
}

if (-not (Test-Path $venv)) {
    Write-Host "Creando entorno virtual en $venv"
    python -m venv $venv
}

Write-Host "Actualizando pip y instalando dependencias..."
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $root "requirements.txt")
# PyInstaller puede no estar en requirements; aseguramos instalación
& $python -m pip install pyinstaller

# Asegurar VC++ Runtime para el instalador (evita crashes de Qt en algunas PCs)
$vcDir = Join-Path $PSScriptRoot "third_party"
$vcExe = Join-Path $vcDir "vc_redist.x64.exe"
if (-not (Test-Path $vcExe)) {
    try {
        New-Item -ItemType Directory -Force -Path $vcDir | Out-Null
        Write-Host "Descargando VC++ Runtime..."
        Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile $vcExe
    } catch {
        Write-Warning "No se pudo descargar vc_redist.x64.exe: $($_.Exception.Message)"
    }
}

# Argumentos --add-data (origen;destino dentro del bundle)
$dataSpec = @(
    "assets;assets",
    "views;views",
    "models;models",
    "utils;utils",
    "workers;workers",
    "ui;ui",
    "config.py;.",
    "config.json;.",
    ".dburl;."
)
$addDataArgs = @()
foreach ($d in $dataSpec) {
    # PyInstaller en Windows usa ';' como separador de origen/destino
    $src = Join-Path $root ($d.Split(';')[0])
    $dest = $d.Split(';')[1]
    if (Test-Path $src) {
        $addDataArgs += "--add-data"
        $addDataArgs += "$src;$dest"
    }
}

# Incluir libpq.dll (Postgres) desde psycopg2-binary para el driver Qt
$libpq = Get-ChildItem -Path (Join-Path $venv "Lib\\site-packages\\psycopg2_binary.libs") -Filter "libpq*.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
$addBinaryArgs = @()
if ($libpq) {
    # Copia adicional con nombre estándar (LIBPQ.dll) para qsqlpsql
    $libpqCopy = Join-Path $libpq.DirectoryName "libpq.dll"
    if (-not (Test-Path $libpqCopy)) {
        Copy-Item $libpq.FullName -Destination $libpqCopy -Force
    }
    # Destino: raíz del bundle para que Qt/psycopg2 lo encuentren
    $addBinaryArgs += "--add-binary"
    $addBinaryArgs += "$($libpq.FullName);."
    if (Test-Path $libpqCopy) {
        $addBinaryArgs += "--add-binary"
        $addBinaryArgs += "$libpqCopy;."
    }
}

# Opciones PyInstaller
$args = @(
    "--noconfirm",
    "--clean",
    "--onedir",
    "--name", "Manarey",
    "--windowed",
    "--icon", (Join-Path $root "assets\\images\\logo_manarey.ico"),
    "--paths", $root,
    "--collect-submodules", "models",
    "--collect-submodules", "views",
    "--collect-submodules", "utils",
    (Join-Path $root "app.py")
) + $addDataArgs + $addBinaryArgs

# La app solo usa QtCore/QtGui/QtWidgets. El hook automatico de PyInstaller
# para PySide6 ya bundlea eso segun los imports. Excluimos explicitamente los
# modulos Qt pesados/no usados (QML, WebEngine, Quick3D, Charts, etc.) para que
# el bundle no crezca de mas ni arrastre plugins QML rotos.
$pysideExcludes = @(
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtQuickControls2", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DExtras",
    "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtPositioning",
    "PySide6.QtSerialPort", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtTest",
    "PySide6.QtDBus", "PySide6.QtNetwork"
)
foreach ($ex in $pysideExcludes) {
    $args += "--exclude-module"
    $args += $ex
}

Write-Host "Ejecutando PyInstaller..."
& $pyinst @args

$distDir = Join-Path $root "dist\Manarey"
$distExe = Join-Path $root "dist\Manarey.exe"
if (Test-Path $distExe) {
    Write-Host "Instalador listo en $distExe (single file)"
} elseif (Test-Path $distDir) {
    Write-Host "Copiando archivos de configuracion al bundle..."
    @(".dburl", "config.json") | ForEach-Object {
        $src = Join-Path $root $_
        if (Test-Path $src) { Copy-Item $src -Destination $distDir -Force }
    }
    if ($libpq) {
        # Asegurar libpq en el bundle final (ambos nombres)
        Copy-Item $libpq.FullName -Destination (Join-Path $distDir $libpq.Name) -Force
        $libpqCopy = Join-Path $libpq.DirectoryName "libpq.dll"
        if (Test-Path $libpqCopy) {
            Copy-Item $libpqCopy -Destination (Join-Path $distDir "libpq.dll") -Force
        }
    }
    Write-Host "Instalador listo en $distDir (ejecutable Manarey.exe)"
} else {
    Write-Warning "No se encontro salida en dist/. Revisa la salida de PyInstaller."
}
