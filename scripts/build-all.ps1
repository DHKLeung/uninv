<#
.SYNOPSIS
    Builds the production release of uninv (backend sidecar + Tauri desktop installers).
.DESCRIPTION
    1. Compiles uninv Python backend into a standalone executable with PyInstaller.
    2. Copies the sidecar binary to desktop/src-tauri/binaries/ with target triple naming.
    3. Executes cargo tauri build to create production Windows installers (.exe and .msi).
.EXAMPLE
    .\scripts\build-all.ps1
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Ensure PATH includes uv and cargo
$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath;$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  UNINV: Building Production Release (v1.2.0)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Resolve target triple from rustc
$rustcOutput = rustc -vV | Out-String
if ($rustcOutput -match "host:\s*([^\r\n]+)") {
    $targetTriple = $matches[1].Trim()
} else {
    $targetTriple = "x86_64-pc-windows-msvc"
}
Write-Host "[Build] Host target triple: $targetTriple" -ForegroundColor Green

# 2. Build Python backend with PyInstaller
Write-Host "`n[1/3] Packaging Python backend with PyInstaller ..." -ForegroundColor Cyan
Push-Location "$root\backend"
try {
    uv run pyinstaller --noconfirm --clean --name uninv-backend --onefile `
        --collect-all uvicorn `
        --collect-all futu `
        --collect-all ib_async `
        entrypoint.py
} finally {
    Pop-Location
}

# 3. Copy sidecar binary to desktop/src-tauri/binaries/
Write-Host "`n[2/3] Staging sidecar binary for Tauri bundler ..." -ForegroundColor Cyan
$binariesDir = "$root\desktop\src-tauri\binaries"
if (-not (Test-Path $binariesDir)) {
    New-Item -ItemType Directory -Force -Path $binariesDir | Out-Null
}
$sourceExe = "$root\backend\dist\uninv-backend.exe"
$destExe = "$binariesDir\uninv-backend-$targetTriple.exe"
Copy-Item -Path $sourceExe -Destination $destExe -Force
Write-Host "[Staged] $destExe" -ForegroundColor Green

# 4. Build Tauri release installer
Write-Host "`n[3/3] Compiling Tauri desktop app and creating installers ..." -ForegroundColor Cyan
Push-Location "$root\desktop\src-tauri"
try {
    cargo tauri build
} finally {
    Pop-Location
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  Build Complete! Windows Installers Ready in:" -ForegroundColor Green
Write-Host "  desktop/src-tauri/target/release/bundle/" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
