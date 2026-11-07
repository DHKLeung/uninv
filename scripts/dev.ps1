<#
.SYNOPSIS
    Run uninv on Windows: Python backend + desktop app.
    All processes are monitored and stopped cleanly together when exiting or pressing Ctrl+C.

.EXAMPLE
    .\scripts\dev.ps1                  # backend + Tauri desktop app
    .\scripts\dev.ps1 -Browser         # backend + UI in browser (no Rust build needed)
    .\scripts\dev.ps1 -ServicesOnly    # backend only (headless, no UI)
#>
param(
    [switch]$Browser,
    [Alias("NoUI")]
    [switch]$ServicesOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Ensure PATH has uv and cargo
$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath;$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"

$backend = $null
$frontend = $null

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  UNINV: Windows Investment Management Environment" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

try {
    # ---------------------------------------------------------
    # 1. Check TWS Status (Port 7496)
    # ---------------------------------------------------------
    $twsLive = (Get-NetTCPConnection -LocalPort 7496 -ErrorAction SilentlyContinue) -ne $null

    if ($twsLive) {
        Write-Host "[IBKR] TWS Live API detected on port 7496" -ForegroundColor Green
    } else {
        Write-Host "[IBKR] Notice: TWS not detected on port 7496." -ForegroundColor Yellow
        Write-Host "       (FastAPI backend will start normally; TWS can be launched anytime)" -ForegroundColor Yellow
    }

    # Check Futubull OpenD Status
    $futuActive = (Get-NetTCPConnection -LocalPort 11111 -ErrorAction SilentlyContinue) -ne $null
    if ($futuActive) {
        Write-Host "[Futu] OpenD API detected on port 11111" -ForegroundColor Green
    }

    # ---------------------------------------------------------
    # 2. Start Python FastAPI Backend (:8000)
    # ---------------------------------------------------------
    $backendPortActive = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue) -ne $null
    if ($backendPortActive) {
        Write-Host "[Backend] FastAPI server already running on http://127.0.0.1:8000" -ForegroundColor Green
    } else {
        Write-Host "[Backend] Starting FastAPI server on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
        $backend = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$root\backend" `
            -FilePath "uv" -ArgumentList "run", "uninv-backend", "--reload"
        Start-Sleep -Seconds 2
        Write-Host "[Backend] API ready at http://127.0.0.1:8000/docs" -ForegroundColor Green
    }

    # ---------------------------------------------------------
    # 3. Start Frontend / UI
    # ---------------------------------------------------------
    if ($ServicesOnly) {
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host "  Backend running. Press Ctrl+C to stop." -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Green
        while ($true) {
            Start-Sleep -Seconds 1
        }
    }
    elseif ($Browser) {
        Write-Host "[UI] Serving UI on http://127.0.0.1:1420 (Ctrl+C to stop) ..." -ForegroundColor Cyan
        $frontend = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$root\backend" `
            -FilePath "uv" -ArgumentList "run", "python", "-m", "http.server", "1420", "--bind", "127.0.0.1", "-d", "..\desktop\src"
        Start-Sleep -Seconds 1
        Start-Process "http://127.0.0.1:1420"
        Wait-Process -Id $frontend.Id
    }
    else {
        Write-Host "[UI] Launching Tauri desktop application ..." -ForegroundColor Cyan
        Push-Location "$root\desktop\src-tauri"
        try {
            cargo tauri --version *> $null
            if ($LASTEXITCODE -eq 0) { cargo tauri dev } else { cargo run }
        }
        finally {
            Pop-Location
        }
    }
}
finally {
    Write-Host "`nShutting down cleanly ..." -ForegroundColor Cyan
    foreach ($p in @($backend, $frontend)) {
        if ($p -and -not $p.HasExited) {
            taskkill /PID $p.Id /T /F *> $null
        }
    }
    Write-Host "All processes stopped." -ForegroundColor Green
}
