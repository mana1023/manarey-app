# Publicar actualización a GitHub Releases
# Uso: .\publish_release.ps1 -Version "1.0.5" -ZipFile "Manarey-1.0.5.zip"

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$ZipFile,
    
    [string]$Changelog = "Nueva versión disponible",
    
    [switch]$Mandatory = $false
)

# Verificar variables de entorno
if (-not $env:GITHUB_REPO) {
    Write-Host "❌ Error: GITHUB_REPO no configurado" -ForegroundColor Red
    Write-Host "Configura con: `$env:GITHUB_REPO = 'usuario/repo'" -ForegroundColor Yellow
    exit 1
}

if (-not $env:GITHUB_TOKEN) {
    Write-Host "❌ Error: GITHUB_TOKEN no configurado" -ForegroundColor Red
    Write-Host "Configura con: `$env:GITHUB_TOKEN = 'tu_token'" -ForegroundColor Yellow
    exit 1
}

# Verificar que el archivo existe
if (-not (Test-Path $ZipFile)) {
    Write-Host "❌ Error: No se encontró $ZipFile" -ForegroundColor Red
    exit 1
}

Write-Host "📤 Publicando en GitHub Releases" -ForegroundColor Green
Write-Host "   Repo: $env:GITHUB_REPO" -ForegroundColor Gray
Write-Host "   Versión: $Version" -ForegroundColor Gray
Write-Host "   Archivo: $ZipFile" -ForegroundColor Gray

# Usar Python para publicar
python publish_github_release.py --version $Version --file $ZipFile --changelog $Changelog $(if ($Mandatory) { "--mandatory" } else { "" })

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Release publicada exitosamente" -ForegroundColor Green
} else {
    Write-Host "❌ Error al publicar release" -ForegroundColor Red
    exit 1
}
