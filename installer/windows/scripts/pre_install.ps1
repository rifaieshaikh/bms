# Pre-install: ensure directories exist
param(
    [Parameter(Mandatory = $true)][string]$DataDir
)

$ErrorActionPreference = "Stop"
$dirs = @(
    "$DataDir\config",
    "$DataDir\logs",
    "$DataDir\data\uploads",
    "$DataDir\data\backups",
    "$DataDir\migrations"
)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
Write-Host "Pre-install directories created under $DataDir"
