<#
.SYNOPSIS
    Orchestrates uninv: launches backend and desktop UI together.
.DESCRIPTION
    Starts the Python FastAPI backend in the background, waits for it to become healthy,
    then launches the Tauri desktop application (or browser UI).
    When exiting or pressing Ctrl+C, all processes are terminated cleanly.
.EXAMPLE
    .\scripts\start-all.ps1             # Backend + Tauri desktop app
    .\scripts\start-all.ps1 -Browser    # Backend + UI in default browser
#>
param(
    [switch]$Browser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Ensure PATH includes uv and cargo
$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath;$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"

$backendProc = $null
$browserProc = $null

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  UNINV: Starting Backend + Desktop Application" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

try {
    # 1. Check Broker Gateways (only active listeners)
    $twsActive = (Get-NetTCPConnection -LocalPort 7496 -State Listen -ErrorAction SilentlyContinue) -ne $null
    if ($twsActive) {
        Write-Host "[IBKR] TWS Live socket detected on port 7496" -ForegroundColor Green
    } else {
        Write-Host "[IBKR] Notice: TWS not detected on port 7496 (launch TWS anytime)" -ForegroundColor Yellow
    }

    # 2. Check if Backend is already active and healthy
    function Test-BackendHealth {
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
            return ($resp.status -eq "ok")
        } catch {
            return $false
        }
    }

    if (Test-BackendHealth) {
        Write-Host "[Backend] FastAPI server already running on http://127.0.0.1:8000" -ForegroundColor Green
    } else {
        # Clean up any orphaned process holding port 8000 in Listen state
        $listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($listeners) {
            foreach ($l in $listeners) {
                if ($l.OwningProcess -gt 0) {
                    Write-Host "[Backend] Terminating unresponsive process holding port 8000 (PID: $($l.OwningProcess)) ..." -ForegroundColor Yellow
                    taskkill /PID $l.OwningProcess /T /F *> $null
                }
            }
            Start-Sleep -Milliseconds 500
        }

        # Resolve uv executable path
        $uvCmd = (Get-Command uv -ErrorAction SilentlyContinue).Source
        if (-not $uvCmd) {
            if (Test-Path "$env:USERPROFILE\.local\bin\uv.exe") {
                $uvCmd = "$env:USERPROFILE\.local\bin\uv.exe"
            } else {
                $uvCmd = "uv"
            }
        }

        Write-Host "[Backend] Starting FastAPI server on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
        $backendProc = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$root\backend" `
            -FilePath $uvCmd -ArgumentList "run", "uninv-backend", "--reload"
        
        # Wait up to 10 seconds for backend health check
        $healthy = $false
        for ($i = 0; $i -lt 20; $i++) {
            Start-Sleep -Milliseconds 500
            if ($backendProc.HasExited) {
                Write-Host "[Backend] Error: Process exited early with code $($backendProc.ExitCode)!" -ForegroundColor Red
                break
            }
            if (Test-BackendHealth) {
                $healthy = $true
                break
            }
        }

        if ($healthy) {
            Write-Host "[Backend] API ready at http://127.0.0.1:8000/docs" -ForegroundColor Green
        } else {
            Write-Host "[Backend] Warning: Health check timed out, continuing anyway..." -ForegroundColor Yellow
        }
    }

    # 3. Start Frontend
    if ($Browser) {
        Write-Host "[UI] Serving web UI on http://127.0.0.1:1420 (Ctrl+C to stop) ..." -ForegroundColor Cyan
        $py = & uv python find
        Start-Process "http://127.0.0.1:1420"
        & $py -m http.server 1420 --bind 127.0.0.1 -d "$root\desktop\src"
    } else {
        Write-Host "[UI] Launching Tauri desktop shell ..." -ForegroundColor Cyan
        Push-Location "$root\desktop\src-tauri"
        try {
            cargo tauri --version *> $null
            if ($LASTEXITCODE -eq 0) {
                cargo tauri dev
            } else {
                cargo run
            }
        } finally {
            Pop-Location
        }
    }
}
finally {
    Write-Host "`n[Shutdown] Stopping background services ..." -ForegroundColor Cyan
    if ($backendProc -and -not $backendProc.HasExited) {
        taskkill /PID $backendProc.Id /T /F *> $null
    }
    Write-Host "[Shutdown] Complete." -ForegroundColor Green
}
