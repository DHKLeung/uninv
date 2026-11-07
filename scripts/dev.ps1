<#
.SYNOPSIS
    Run uninv in one click: broker gateways + Python backend + desktop app.
    All processes are monitored and stopped cleanly together when exiting or pressing Ctrl+C.

.EXAMPLE
    .\scripts\dev.ps1                  # gateways + backend + Tauri desktop app
    .\scripts\dev.ps1 -Browser         # gateways + backend + UI in browser (no Rust build)
    .\scripts\dev.ps1 -ServicesOnly    # gateways + backend only (headless, no UI)
    .\scripts\dev.ps1 -NoGateway       # backend + UI only (skip broker gateways)
#>
param(
    [switch]$Browser,
    [Alias("NoUI")]
    [switch]$ServicesOnly,
    [switch]$NoGateway
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Ensure PATH has Java, uv, and cargo available
$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath;$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    $foundJava = Get-ChildItem "C:\Program Files\Microsoft" -Recurse -Filter "java.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($foundJava) {
        $javaBin = Split-Path $foundJava.FullName
        $env:Path = "$javaBin;$env:Path"
        $env:JAVA_HOME = Split-Path $javaBin
    }
}

$ibkrGateway = $null
$backend = $null
$frontend = $null

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  UNINV: Unified Investing Development Environment" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

try {
    # ---------------------------------------------------------
    # 1. Start Broker Gateways
    # ---------------------------------------------------------
    if (-not $NoGateway) {
        # Check IBKR Client Portal Gateway (:5000)
        $ibkrDir = Join-Path $root "gateways\ibkr-gateway"
        if (Test-Path $ibkrDir) {
            $ibkrPortActive = (Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue) -ne $null
            if ($ibkrPortActive) {
                Write-Host "[IBKR] Gateway already running on https://localhost:5000" -ForegroundColor Green
            } else {
                Write-Host "[IBKR] Starting Client Portal Gateway on https://localhost:5000 ..." -ForegroundColor Cyan
                $ibkrGateway = Start-Process -PassThru -NoNewWindow -WorkingDirectory $ibkrDir `
                    -FilePath "cmd.exe" -ArgumentList "/c", "bin\run.bat", "root\conf.yaml"
                
                # Wait briefly for port 5000
                $sw = [System.Diagnostics.Stopwatch]::StartNew()
                while ($sw.ElapsedMilliseconds -lt 6000) {
                    Start-Sleep -Milliseconds 500
                    if ((Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue) -ne $null) {
                        break
                    }
                }
                Write-Host "[IBKR] Gateway listening on https://localhost:5000" -ForegroundColor Green
                Write-Host "       (Log in at https://localhost:5000 to authenticate 2FA)" -ForegroundColor Yellow
            }
        }

        # Check Futubull Gateway (:11111) when present
        $futuDir = Join-Path $root "gateways\futubull-gateway"
        if (Test-Path $futuDir) {
            $futuPortActive = (Get-NetTCPConnection -LocalPort 11111 -ErrorAction SilentlyContinue) -ne $null
            if ($futuPortActive) {
                Write-Host "[Futubull] Gateway already running on 127.0.0.1:11111" -ForegroundColor Green
            }
        }
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
        Write-Host "  All services and gateways running. Press Ctrl+C to stop." -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Green
        # Wait until user interrupts
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
    Write-Host "`nShutting down all services and gateways cleanly ..." -ForegroundColor Cyan
    foreach ($p in @($backend, $ibkrGateway, $frontend)) {
        if ($p -and -not $p.HasExited) {
            if ($IsWindows -or ($null -eq $IsWindows -and $env:OS -match 'Windows')) {
                taskkill /PID $p.Id /T /F *> $null
            } else {
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Write-Host "All services stopped." -ForegroundColor Green
}
