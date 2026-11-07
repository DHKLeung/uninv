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

# Check broker gateway status
$twsActive = (Get-NetTCPConnection -LocalPort 7496 -ErrorAction SilentlyContinue) -ne $null
if ($twsActive) {
    Write-Host "[IBKR] TWS Live socket detected on port 7496" -ForegroundColor Green
} else {
    Write-Host "[IBKR] Notice: TWS not detected on port 7496 (launch TWS anytime)" -ForegroundColor Yellow
}

$futuActive = (Get-NetTCPConnection -LocalPort 11111 -ErrorAction SilentlyContinue) -ne $null
if ($futuActive) {
    Write-Host "[Futu] OpenD socket detected on port 11111" -ForegroundColor Green
}

# Check if backend is already running
$alreadyRunning = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue) -ne $null
if ($alreadyRunning) {
    Write-Host "[Backend] Server already running at http://127.0.0.1:8000" -ForegroundColor Green
    Write-Host "[Backend] Interactive docs at http://127.0.0.1:8000/docs" -ForegroundColor Cyan
    exit 0
}

Write-Host "[Backend] Launching FastAPI at http://127.0.0.1:8000 (Ctrl+C to stop) ..." -ForegroundColor Cyan
Write-Host "[Backend] Interactive docs: http://127.0.0.1:8000/docs" -ForegroundColor Green

Set-Location "$root\backend"
& uv run uninv-backend --reload
