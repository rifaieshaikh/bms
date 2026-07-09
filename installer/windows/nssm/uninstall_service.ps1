# Uninstall VayBooksBMS Windows service
param(
    [Parameter(Mandatory = $true)][string]$InstallDir
)

$ErrorActionPreference = "Stop"
$nssm = Join-Path $InstallDir "tools\nssm.exe"
$serviceName = "VayBooksBMS"

$existing = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existing) {
    & $nssm stop $serviceName confirm
    & $nssm remove $serviceName confirm
    Write-Host "Service $serviceName removed."
} else {
    Write-Host "Service $serviceName not found."
}
