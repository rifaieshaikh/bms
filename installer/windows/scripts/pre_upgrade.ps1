# Pre-upgrade: stop service and backup user data
param(
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [Parameter(Mandatory = $true)][string]$DataDir,
    [string]$AppVersion = "unknown"
)

$ErrorActionPreference = "Stop"
$nssm = Join-Path $InstallDir "tools\nssm.exe"
$serviceName = "VayBooksBMS"

if (Test-Path $nssm) {
    & $nssm stop $serviceName confirm
}

$backupDir = Join-Path $DataDir "data\backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipPath = Join-Path $backupDir "pre_upgrade_${AppVersion}_${stamp}.zip"

$items = @()
$configPath = Join-Path $DataDir "config\config.toml"
if (Test-Path $configPath) { $items += $configPath }
$uploads = Join-Path $DataDir "data\uploads"
if (Test-Path $uploads) { $items += $uploads }

if ($items.Count -gt 0) {
    Compress-Archive -Path $items -DestinationPath $zipPath -Force
    Write-Host "Pre-upgrade backup: $zipPath"
}

Write-Host "Pre-upgrade complete."
