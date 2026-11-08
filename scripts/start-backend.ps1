<#
.SYNOPSIS
    Starts the uninv Python FastAPI backend.
.DESCRIPTION
    Runs uninv-backend via uv on http://127.0.0.1:8000.
    Checks connectivity to broker daemons (IBKR TWS on 7496, Futu OpenD on 11111).
.EXAMPLE
    .\scripts\start-backend.ps1
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Ensure PATH includes uv and user local binaries
$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath;$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  UNINV: Starting Python FastAPI Backend" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check broker gateway status (only active listeners)
$twsActive = (Get-NetTCPConnection -LocalPort 7496 -State Listen -ErrorAction SilentlyContinue) -ne $null
if ($twsActive) {
    Write-Host "[IBKR] TWS Live socket detected on port 7496" -ForegroundColor Green
} else {
    Write-Host "[IBKR] Notice: TWS not detected on port 7496 (launch TWS anytime)" -ForegroundColor Yellow
}

$futuActive = (Get-NetTCPConnection -LocalPort 11111 -State Listen -ErrorAction SilentlyContinue) -ne $null
if ($futuActive) {
    Write-Host "[Futu] OpenD socket detected on port 11111" -ForegroundColor Green
}

# Check if backend is already running and healthy
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
    if ($resp.status -eq "ok") {
        Write-Host "[Backend] Server already running at http://127.0.0.1:8000" -ForegroundColor Green
        Write-Host "[Backend] Interactive docs at http://127.0.0.1:8000/docs" -ForegroundColor Cyan
        exit 0
    }
} catch {}

# Clean up any unresponsive process holding port 8000
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

Write-Host "[Backend] Launching FastAPI at http://127.0.0.1:8000 (Ctrl+C to stop) ..." -ForegroundColor Cyan
Write-Host "[Backend] Interactive docs: http://127.0.0.1:8000/docs" -ForegroundColor Green

Set-Location "$root\backend"
& uv run uninv-backend --reload
