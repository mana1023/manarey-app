param(
    [string]$Version,
    [string]$Notes = "",
    [string]$InstallerPath,
    [string]$GithubRepo,
    [string]$GithubToken,
    [switch]$Mandatory,
    [switch]$SkipBuild,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
function Read-VersionFromFile($path) {
    if (-not (Test-Path $path)) { return $null }
    $txt = Get-Content $path -Raw
    if ($txt -match '__version__\s*=\s*"([^"]+)"') {
        return $matches[1]
    }
    return $null
}

function Get-LatestSetup($folder) {
    if (-not (Test-Path $folder)) { return $null }
    $item = Get-ChildItem -Path $folder -Filter "Manarey-Setup-*.exe" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($item) { return $item.FullName }
    return $null
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $Version) {
    $Version = Read-VersionFromFile (Join-Path $root "version.py")
}
if (-not $Version) {
    throw "No se pudo determinar la version. Usa -Version."
}

if (-not $SkipBuild) {
    $buildScript = Join-Path $root "Oficial\build_installer.ps1"
    if (Test-Path $buildScript) {
        if ($Clean) { & $buildScript -Clean } else { & $buildScript }
    } else {
        Write-Warning "No se encontro Oficial\\build_installer.ps1; se continua sin build."
    }

    # Intentar generar instalador NSIS si makensis existe
    $nsis = $null
    try { $nsis = (Get-Command "makensis" -ErrorAction SilentlyContinue).Source } catch {}
    if (-not $nsis) {
        $candidates = @(
            "C:\\Program Files (x86)\\NSIS\\makensis.exe",
            "C:\\Program Files\\NSIS\\makensis.exe"
        )
        foreach ($c in $candidates) { if (Test-Path $c) { $nsis = $c; break } }
    }
    $nsi = Join-Path $root "Oficial\\ManareyInstaller.nsi"
    if ($nsis -and (Test-Path $nsi)) {
        try {
            $txt = Get-Content $nsi -Raw
            $repApp = ('!define APP_VERSION "' + $Version + '"')
            $repRoot = ('!define ROOT_DIR "' + $root + '"')
            $txt = [regex]::Replace($txt, '!define\s+APP_VERSION\s+"[^"]+"', { param($m) $repApp })
            $txt = [regex]::Replace($txt, '!define\s+ROOT_DIR\s+"[^"]+"', { param($m) $repRoot })
            Set-Content -Path $nsi -Value $txt -Encoding UTF8
            & $nsis $nsi | Out-Null
        } catch {
            Write-Warning "NSIS fallo: $($_.Exception.Message)"
        }
    } else {
        Write-Warning "NSIS (makensis) no encontrado. Se publicara el instalador existente si hay."
    }
}

if (-not $InstallerPath) {
    $candidate = Join-Path $root ("DESCARGABLE\Manarey-Setup-$Version.exe")
    if (Test-Path $candidate) {
        $InstallerPath = $candidate
    } else {
        $InstallerPath = Get-LatestSetup (Join-Path $root "DESCARGABLE")
    }
}
if (-not $InstallerPath) {
    $fallback = Join-Path $root "dist\Manarey.exe"
    if (Test-Path $fallback) { $InstallerPath = $fallback }
}
if (-not $InstallerPath -or -not (Test-Path $InstallerPath)) {
    throw "No se encontro instalador. Pasa -InstallerPath o coloca el setup en DESCARGABLE."
}

# Evitar publicar una version con un instalador de otra version
try {
    $fname = Split-Path -Leaf $InstallerPath
    if ($fname -notmatch [regex]::Escape($Version)) {
        throw "El instalador ($fname) no coincide con la version $Version. Cancelo publicacion."
    }
} catch {
    throw $_
}

$checksum = ""
try {
    $checksum = (Get-FileHash -Algorithm SHA256 -Path $InstallerPath).Hash.ToLower()
} catch {
    $checksum = ""
}

$py = Join-Path $root "Oficial\\.venv_inst\\Scripts\\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

if (-not $GithubRepo) { $GithubRepo = $env:GITHUB_REPO }
if (-not $GithubToken) { $GithubToken = $env:GITHUB_TOKEN }
if (-not $GithubRepo -or -not $GithubToken) {
    throw "Faltan GITHUB_REPO y/o GITHUB_TOKEN. Pasa -GithubRepo y -GithubToken o define variables de entorno."
}

try {
    & $py -c "import requests" | Out-Null
} catch {
    & $py -m pip install requests | Out-Null
}

$env:GITHUB_REPO = $GithubRepo
$env:GITHUB_TOKEN = $GithubToken

$ghScript = Join-Path $root "scripts\\publish_github_release.py"
if (-not (Test-Path $ghScript)) {
    throw "No se encontro scripts\\publish_github_release.py"
}

$tag = "v$Version"
$downloadUrl = & $py $ghScript --file $InstallerPath --tag $tag --name "Manarey $Version" --body $Notes
if (-not $downloadUrl) {
    throw "No se pudo obtener la URL de descarga desde GitHub."
}

$pubScript = Join-Path $root "scripts\\publish_update_url.py"
if (-not (Test-Path $pubScript)) {
    throw "No se encontro scripts\\publish_update_url.py"
}

$args = @(
    $pubScript,
    "--version", $Version,
    "--download-url", $downloadUrl,
    "--changelog", $Notes,
    "--checksum", $checksum
)
if ($Mandatory) { $args += "--mandatory" }

& $py @args | Out-Null

Write-Host "Actualizacion publicada en GitHub + Supabase."
Write-Host "Version: $Version"
Write-Host "Instalador: $InstallerPath"
Write-Host "URL: $downloadUrl"
