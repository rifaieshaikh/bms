# Stop all Streamlit processes and restart BMS (streamlit run app.py).
# Usage (from anywhere):
#   powershell -File path\to\bms\restart_bms.ps1
# Or from bms/:
#   .\restart_bms.ps1

param(
    [int]$Port = 8501,
    [switch]$NoHeadless
)

$ErrorActionPreference = "Stop"
$AppDir = $PSScriptRoot
Set-Location $AppDir

function Stop-StreamlitProcesses {
    $stopped = @()

    # Match python/streamlit processes whose command line looks like Streamlit
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $cmd = $_.CommandLine
            $cmd -and (
                $cmd -match '(?i)[\\/ ]streamlit(\.exe)?(\s|$)' -or
                $cmd -match '(?i)-m\s+streamlit\b'
            )
        } |
        ForEach-Object {
            Write-Host "Stopping PID $($_.ProcessId): $($_.Name)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            $stopped += $_.ProcessId
        }

    # Named streamlit executable (if present)
    Get-Process -Name "streamlit" -ErrorAction SilentlyContinue |
        ForEach-Object {
            Write-Host "Stopping streamlit PID $($_.Id)"
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            $stopped += $_.Id
        }

    # Anything still bound to the app port
    try {
        $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $listeners) {
            $owningPid = $conn.OwningProcess
            if ($owningPid -and $owningPid -notin $stopped) {
                Write-Host "Stopping port $Port owner PID $owningPid"
                Stop-Process -Id $owningPid -Force -ErrorAction SilentlyContinue
                $stopped += $owningPid
            }
        }
    } catch {
        # Get-NetTCPConnection may be unavailable; ignore
    }

    if ($stopped.Count -eq 0) {
        Write-Host "No Streamlit processes found."
    } else {
        Write-Host "Stopped $($stopped.Count) process(es)."
        Start-Sleep -Seconds 1
    }
}

Write-Host "=== Stopping Streamlit ==="
Stop-StreamlitProcesses

$streamlitArgs = @("run", "app.py", "--server.port", "$Port")
if (-not $NoHeadless) {
    $streamlitArgs += @("--server.headless", "true")
}

Write-Host "=== Starting BMS on port $Port ==="
Write-Host "Working directory: $AppDir"
Write-Host "Command: streamlit $($streamlitArgs -join ' ')"
Write-Host "Local URL: http://localhost:$Port"
Write-Host ""

& streamlit @streamlitArgs
