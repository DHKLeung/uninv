<#
.SYNOPSIS
    Starts the uninv Tauri desktop application (or browser UI).
.DESCRIPTION
    Runs the native Tauri 2 desktop shell. If -Browser is passed, serves the HTML/JS
    UI on http://127.0.0.1:1420 using python's built-in http server.
.EXAMPLE
    .\scripts\start-desktop.ps1             # Native Tauri desktop window
    .\scripts\start-desktop.ps1 -Browser    # In-browser UI on http://127.0.0.1:1420
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

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  UNINV: Starting Desktop Application" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check backend status via health check
$backendActive = $false
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:7541/health" -TimeoutSec 2 -ErrorAction Stop
    $backendActive = ($resp.status -eq "ok")
} catch {
    $backendActive = (Get-NetTCPConnection -LocalPort 7541 -State Listen -ErrorAction SilentlyContinue) -ne $null
}

if (-not $backendActive) {
    Write-Host "[Warning] Backend is not running on http://127.0.0.1:7541." -ForegroundColor Yellow
    Write-Host "          Start it in another terminal with .\scripts\start-backend.ps1" -ForegroundColor Yellow
    Write-Host "          or run both together with .\scripts\start-all.ps1" -ForegroundColor Yellow
} else {
    Write-Host "[Backend] Connected to active backend at http://127.0.0.1:7541" -ForegroundColor Green
}

if ($Browser) {
    Write-Host "[UI] Serving web UI on http://127.0.0.1:1420 (Ctrl+C to stop) ..." -ForegroundColor Cyan
    $py = & uv python find
    Start-Process "http://127.0.0.1:1420"
    & $py -m http.server 1420 --bind 127.0.0.1 -d "$root\desktop\src"
} else {
    Write-Host "[UI] Launching Tauri desktop shell ..." -ForegroundColor Cyan
    Set-Location "$root\desktop\src-tauri"
    cargo tauri --version *> $null
    if ($LASTEXITCODE -eq 0) {
        cargo tauri dev
    } else {
        cargo run
    }
}
