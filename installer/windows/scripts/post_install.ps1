# Post-install: write config, register service, create shortcuts
param(
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [Parameter(Mandatory = $true)][string]$DataDir,
    [Parameter(Mandatory = $true)][string]$MongoMode,
    [string]$MongoUri = "mongodb://localhost:27017",
    [string]$DbName = "zahcci_customization",
    [int]$AppPort = 8501,
    [string]$AppVersion = "1.0.0"
)

$ErrorActionPreference = "Stop"
$configPath = Join-Path $DataDir "config\config.toml"
$updateUrl = "https://github.com/rifaieshaikh/bms/releases/latest/download/version.json"

$config = @"
APP_VERSION = "$AppVersion"
APP_PORT = $AppPort
MONGO_URI = "$MongoUri"
DB_NAME = "$DbName"
MONGO_MODE = "$MongoMode"
UPDATE_CHECK_URL = "$updateUrl"
BACKUP_SCHEDULE = "daily"
BACKUP_RETENTION_DAYS = 30
AUTO_UPDATE_ENABLED = false
"@
Set-Content -Path $configPath -Value $config -Encoding UTF8

& (Join-Path $InstallDir "nssm\install_service.ps1") `
    -InstallDir $InstallDir -DataDir $DataDir -AppPort $AppPort

$launcher = Join-Path $InstallDir "tools\VayBooks-Launcher.exe"
if (-not (Test-Path $launcher)) {
    $launcherPy = Join-Path $InstallDir "tools\launcher.py"
    if (Test-Path $launcherPy) {
        $launcher = Join-Path $InstallDir "python\python.exe"
        $launcherArgs = Join-Path $InstallDir "tools\launcher.py"
    }
}

$wsh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = $wsh.CreateShortcut((Join-Path $desktop "VayBooks-BMS.lnk"))
if ($launcherArgs) {
    $shortcut.TargetPath = $launcher
    $shortcut.Arguments = "`"$launcherArgs`""
} else {
    $shortcut.TargetPath = $launcher
}
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Save()

$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "VayBooks-BMS"
New-Item -ItemType Directory -Force -Path $startMenu | Out-Null
$smShortcut = $wsh.CreateShortcut((Join-Path $startMenu "VayBooks-BMS.lnk"))
if ($launcherArgs) {
    $smShortcut.TargetPath = $launcher
    $smShortcut.Arguments = "`"$launcherArgs`""
} else {
    $smShortcut.TargetPath = $launcher
}
$smShortcut.WorkingDirectory = $InstallDir
$smShortcut.Save()

Write-Host "Post-install complete."
