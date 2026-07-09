# Install VayBooksBMS Windows service via NSSM
param(
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [Parameter(Mandatory = $true)][string]$DataDir,
    [int]$AppPort = 8501
)

$ErrorActionPreference = "Stop"
$nssm = Join-Path $InstallDir "tools\nssm.exe"
$python = Join-Path $InstallDir "python\python.exe"
$appDir = Join-Path $InstallDir "app"
$logDir = Join-Path $DataDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$serviceName = "VayBooksBMS"
$existing = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existing) {
    & $nssm stop $serviceName confirm
    & $nssm remove $serviceName confirm
}

& $nssm install $serviceName $python `
    "-m" "streamlit" "run" "app.py" "--server.headless=true" "--server.port=$AppPort"
& $nssm set $serviceName AppDirectory $appDir
& $nssm set $serviceName AppEnvironmentExtra "VAYBOOKS_DATA_DIR=$DataDir"
& $nssm set $serviceName Start SERVICE_AUTO_START
& $nssm set $serviceName AppStdout (Join-Path $logDir "service.log")
& $nssm set $serviceName AppStderr (Join-Path $logDir "service.log")
& $nssm set $serviceName AppRotateFiles 1
& $nssm set $serviceName AppRotateBytes 10485760
& $nssm set $serviceName AppExit Default Restart
& $nssm set $serviceName AppRestartDelay 5000

Start-Service $serviceName
Write-Host "Service $serviceName installed and started."
