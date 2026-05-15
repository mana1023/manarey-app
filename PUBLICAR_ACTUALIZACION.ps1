<#
.SYNOPSIS
    Compila y publica una nueva versión de Manarey en GitHub.
    Doble clic en PUBLICAR_ACTUALIZACION.bat para ejecutar.
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# ─── Colores ─────────────────────────────────────────────────────────────────
function Write-Step($msg)    { Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Write-Ok($msg)      { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail($msg)    { Write-Host "`n❌ $msg" -ForegroundColor Red }

# ─── Leer versión ────────────────────────────────────────────────────────────
$versionFile = Join-Path $root "version.py"
$versionMatch = (Get-Content $versionFile -Raw) -match '__version__\s*=\s*"([^"]+)"'
if (-not $versionMatch) { Write-Fail "No se pudo leer version.py"; exit 1 }
$Version = $Matches[1]

Write-Host ""
Write-Host "═══════════════════════════════════════════" -ForegroundColor DarkYellow
Write-Host "   MANAREY — Publicar v$Version" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════" -ForegroundColor DarkYellow

# ─── GitHub Token ─────────────────────────────────────────────────────────────
$tokenFile = Join-Path $root ".github_token"
$GithubToken = ""

if (Test-Path $tokenFile) {
    $GithubToken = (Get-Content $tokenFile -Raw).Trim()
    Write-Ok "Token de GitHub leído desde .github_token"
} elseif ($env:GITHUB_TOKEN) {
    $GithubToken = $env:GITHUB_TOKEN
    Write-Ok "Token de GitHub leído desde variable de entorno"
} else {
    Write-Host ""
    Write-Host "  Se necesita un GitHub Token con permisos 'repo'." -ForegroundColor Yellow
    Write-Host "  Obtené uno en: https://github.com/settings/tokens" -ForegroundColor DarkGray
    Write-Host ""
    $GithubToken = Read-Host "  Pegá tu GitHub Token"
    if (-not $GithubToken) { Write-Fail "Token requerido."; exit 1 }
    # Guardar para la próxima vez
    $GithubToken | Out-File $tokenFile -Encoding utf8 -NoNewline
    Write-Ok "Token guardado en .github_token (no se sube a git)"
}

$env:GITHUB_TOKEN = $GithubToken
$env:GITHUB_REPO  = "mana1023/manarey-updates"

# ─── Changelog ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Escribí las notas de esta versión (Enter para omitir):" -ForegroundColor Cyan
$Notes = Read-Host "  Notas"
if (-not $Notes) { $Notes = "Mejoras y correcciones v$Version" }

# ─── Confirmar ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Versión  : $Version" -ForegroundColor White
Write-Host "  Notas    : $Notes"   -ForegroundColor White
Write-Host "  Repo     : mana1023/manarey-updates" -ForegroundColor White
Write-Host ""
$confirm = Read-Host "  ¿Continuar? (s/n)"
if ($confirm -notmatch "^[sS]") { Write-Host "Cancelado."; exit 0 }

# ─── Paso 1: Compilar con build_installer.ps1 ────────────────────────────────
Write-Step "Compilando con PyInstaller..."
$buildScript = Join-Path $root "Oficial\build_installer.ps1"
if (-not (Test-Path $buildScript)) {
    Write-Fail "No se encontró Oficial\build_installer.ps1"
    exit 1
}
try {
    & $buildScript
    Write-Ok "Compilación completa"
} catch {
    Write-Fail "Error al compilar: $($_.Exception.Message)"
    exit 1
}

# ─── Paso 2: Crear instalador NSIS ────────────────────────────────────────────
Write-Step "Creando instalador con NSIS..."
$nsis = $null
@("C:\Program Files (x86)\NSIS\makensis.exe", "C:\Program Files\NSIS\makensis.exe") | ForEach-Object {
    if (Test-Path $_) { $nsis = $_ }
}
if (-not $nsis) {
    try { $nsis = (Get-Command "makensis" -ErrorAction SilentlyContinue).Source } catch {}
}

$nsiFile = Join-Path $root "Oficial\ManareyInstaller.nsi"
if ($nsis -and (Test-Path $nsiFile)) {
    # Parchear versión y ruta en el .nsi
    $nsiContent = Get-Content $nsiFile -Raw
    $nsiContent = [regex]::Replace($nsiContent, '!define\s+APP_VERSION\s+"[^"]+"', "!define APP_VERSION `"$Version`"")
    $nsiContent = [regex]::Replace($nsiContent, '!define\s+ROOT_DIR\s+"[^"]+"', "!define ROOT_DIR `"$root`"")
    Set-Content -Path $nsiFile -Value $nsiContent -Encoding UTF8

    & $nsis $nsiFile
    Write-Ok "Instalador NSIS creado"
} else {
    Write-Warn "NSIS no encontrado o falta el .nsi. Se saltea la generación del instalador."
}

# ─── Paso 3: Buscar instalador ────────────────────────────────────────────────
Write-Step "Buscando instalador Manarey-Setup-$Version.exe..."
$installerPath = Join-Path $root "DESCARGABLE\Manarey-Setup-$Version.exe"
if (-not (Test-Path $installerPath)) {
    $latest = Get-ChildItem -Path (Join-Path $root "DESCARGABLE") -Filter "Manarey-Setup-*.exe" -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        Write-Warn "No se encontró Manarey-Setup-$Version.exe, usando $($latest.Name)"
        $installerPath = $latest.FullName
    } else {
        Write-Fail "No se encontró ningún instalador en DESCARGABLE/"
        Write-Host "  El instalador debe llamarse: Manarey-Setup-$Version.exe"
        exit 1
    }
}

$sizeMB = [math]::Round((Get-Item $installerPath).Length / 1MB, 1)
Write-Ok "Instalador: $(Split-Path -Leaf $installerPath) ($sizeMB MB)"

# ─── Paso 4: Calcular checksum del instalador ─────────────────────────────────
$checksum = (Get-FileHash -Algorithm SHA256 -Path $installerPath).Hash.ToLower()
Write-Ok "SHA256 instalador: $checksum"

# Guardar checksum en archivo para subirlo como asset
$checksumFile = Join-Path $env:TEMP "Manarey-Setup-$Version.exe.sha256"
"$checksum  Manarey-Setup-$Version.exe" | Out-File $checksumFile -Encoding ascii -NoNewline

# ─── Paso 4b: Generar delta.zip (solo archivos de código de la app) ───────────
Write-Step "Generando delta.zip con archivos de la app..."
$internalDir = Join-Path $root "dist\Manarey\_internal"
$deltaZipPath = Join-Path $env:TEMP "delta.zip"
$deltaChecksumFile = Join-Path $env:TEMP "delta.zip.sha256"

$deltaOk = $false
if (Test-Path $internalDir) {
    # Directorios de código de la app (sin runtime de Python ni PyQt5)
    $appDirs = @("models", "views", "utils", "workers", "ui")
    $appFiles = @("version.py", "version.pyc")

    if (Test-Path $deltaZipPath) { Remove-Item $deltaZipPath -Force }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zipStream = [System.IO.Compression.ZipFile]::Open($deltaZipPath, [System.IO.Compression.ZipArchiveMode]::Create)

    $addedFiles = 0
    foreach ($dir in $appDirs) {
        $dirPath = Join-Path $internalDir $dir
        if (Test-Path $dirPath) {
            Get-ChildItem -Recurse -File -Path $dirPath | ForEach-Object {
                $relPath = $_.FullName.Substring($internalDir.Length + 1)
                [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipStream, $_.FullName, $relPath) | Out-Null
                $addedFiles++
            }
        }
    }
    foreach ($fname in $appFiles) {
        $fpath = Join-Path $internalDir $fname
        if (Test-Path $fpath) {
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zipStream, $fpath, $fname) | Out-Null
            $addedFiles++
        }
    }

    $zipStream.Dispose()

    if ($addedFiles -gt 0) {
        $deltaSizeMB = [math]::Round((Get-Item $deltaZipPath).Length / 1MB, 2)
        $deltaChecksum = (Get-FileHash -Algorithm SHA256 -Path $deltaZipPath).Hash.ToLower()
        "$deltaChecksum  delta.zip" | Out-File $deltaChecksumFile -Encoding ascii -NoNewline
        Write-Ok "delta.zip: $addedFiles archivos, $deltaSizeMB MB (SHA256: $deltaChecksum)"
        $deltaOk = $true
    } else {
        Write-Warn "No se encontraron archivos de código en $internalDir — se omite delta.zip"
        if (Test-Path $deltaZipPath) { Remove-Item $deltaZipPath -Force }
    }
} else {
    Write-Warn "dist\Manarey\_internal\ no existe — se omite delta.zip"
    Write-Warn "  Asegurate de compilar con PyInstaller antes de publicar."
}

# ─── Paso 5: Publicar en GitHub ───────────────────────────────────────────────
Write-Step "Publicando en GitHub Releases..."
$ghScript = Join-Path $root "scripts\publish_github_release.py"
if (-not (Test-Path $ghScript)) {
    Write-Fail "No se encontró scripts\publish_github_release.py"
    exit 1
}

$tag = "v$Version"
$downloadUrl = & python $ghScript --file $installerPath --tag $tag --name "Manarey $Version" --body $Notes
if (-not $downloadUrl -or $LASTEXITCODE -ne 0) {
    Write-Fail "Error al publicar en GitHub. Revisá el token y la conexión."
    exit 1
}
Write-Ok "Publicado en GitHub: $downloadUrl"

# ─── Paso 5b: Subir assets adicionales (checksum + delta) ─────────────────────
Write-Step "Subiendo assets adicionales al release..."
$apiHeaders = @{
    Authorization  = "Bearer $GithubToken"
    "User-Agent"   = "Manarey-Updater/1.0"
    Accept         = "application/vnd.github.v3+json"
}

try {
    $releaseInfo = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/$($env:GITHUB_REPO)/releases/tags/$tag" `
        -Headers $apiHeaders
    # upload_url tiene formato: https://uploads.github.com/repos/.../assets{?name,label}
    $uploadBase = $releaseInfo.upload_url -replace '\{.*\}', ''

    function Upload-Asset($filePath, $assetName, $contentType) {
        try {
            $up = Invoke-RestMethod `
                -Uri "${uploadBase}?name=$assetName" `
                -Method Post `
                -Headers ($apiHeaders + @{ "Content-Type" = $contentType }) `
                -InFile $filePath
            Write-Ok "Subido: $assetName"
            return $up.browser_download_url
        } catch {
            Write-Warn "No se pudo subir $assetName`: $($_.Exception.Message)"
            return $null
        }
    }

    Upload-Asset $checksumFile "Manarey-Setup-$Version.exe.sha256" "text/plain" | Out-Null

    if ($deltaOk) {
        Upload-Asset $deltaZipPath "delta.zip" "application/zip" | Out-Null
        Upload-Asset $deltaChecksumFile "delta.zip.sha256" "text/plain" | Out-Null
        Write-Ok "Assets de delta subidos al release"
    }
} catch {
    Write-Warn "No se pudieron subir assets adicionales: $($_.Exception.Message)"
}

# ─── Paso 6: Registrar en Supabase (opcional) ─────────────────────────────────
$pubScript = Join-Path $root "scripts\publish_update_url.py"
if (Test-Path $pubScript) {
    Write-Step "Registrando en base de datos..."
    try {
        $pubArgs = @($pubScript, "--version", $Version, "--download-url", $downloadUrl, "--changelog", $Notes, "--checksum", $checksum)
        & python @pubArgs | Out-Null
        Write-Ok "Registrado en Supabase"
    } catch {
        Write-Warn "No se pudo registrar en Supabase (no crítico): $($_.Exception.Message)"
    }
}

# ─── Listo ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════" -ForegroundColor DarkYellow
Write-Host "   ✓ Actualización v$Version publicada" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "  URL      : $downloadUrl" -ForegroundColor White
if ($deltaOk) {
    Write-Host "  Delta    : delta.zip subido (actualización rápida)" -ForegroundColor White
}
Write-Host "  Release  : https://github.com/mana1023/manarey-updates/releases/tag/$tag" -ForegroundColor White
Write-Host ""
Write-Host "  Las PCs con Manarey instalado recibirán la actualización" -ForegroundColor DarkGray
Write-Host "  automáticamente en el próximo inicio de la app." -ForegroundColor DarkGray
Write-Host "  Si hay delta.zip, la descarga será ~10x más rápida." -ForegroundColor DarkGray
Write-Host ""
Read-Host "  Presioná Enter para cerrar"
