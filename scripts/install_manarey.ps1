# scripts/install_manarey.ps1 (versión recomendada)
$ErrorActionPreference = 'Stop'

function New-Shortcut($Path, $Target, $WorkingDir, $Icon) {
  $ws = New-Object -ComObject WScript.Shell
  $s = $ws.CreateShortcut($Path)
  $s.TargetPath = $Target
  if ($WorkingDir) { $s.WorkingDirectory = $WorkingDir }
  if ($Icon) { $s.IconLocation = $Icon }
  $s.Save()
}

# Ubicaciones (se asume que el script está en scripts\install_manarey.ps1)
$SourceDir = Join-Path $PSScriptRoot '..\dist\Manarey'
$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\Manarey'
$StartMenuDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Manarey'
$DesktopDir = [Environment]::GetFolderPath('Desktop')

if (-not (Test-Path $SourceDir)) {
  throw "No se encontró la carpeta fuente: $SourceDir. Verificá que 'dist\Manarey' exista y que mantengas la estructura del ZIP."
}

# Intentar cerrar Manarey si está corriendo
try {
  Get-Process -Name 'Manarey' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
} catch {
  # no crashear si no se puede detener; sólo continuar
}

# Crear carpeta destino y copiar archivos
try {
  New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
  Copy-Item -Path (Join-Path $SourceDir '*') -Destination $InstallDir -Recurse -Force
} catch {
  throw "Error al copiar archivos a $InstallDir. Detalle: $($_.Exception.Message)"
}

# Crear accesos directos
try {
  New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null
  $exe = Join-Path $InstallDir 'Manarey.exe'
  New-Shortcut (Join-Path $StartMenuDir 'Manarey.lnk') $exe $InstallDir "$exe,0"
  New-Shortcut (Join-Path $DesktopDir 'Manarey.lnk') $exe $InstallDir "$exe,0"
} catch {
  throw "Error al crear accesos directos. Detalle: $($_.Exception.Message)"
}

Write-Host "Instalación per-user completada en: $InstallDir" -ForegroundColor Green
Write-Host "Accesos directos creados en el Menú Inicio y el Escritorio." -ForegroundColor Green

# Lanzar la app (opcional)
Start-Process $exe
