<#
.SYNOPSIS
    Run uninv in development mode: Python backend + desktop app, stopped together with Ctrl+C.

.EXAMPLE
    .\scripts\dev.ps1            # backend + Tauri desktop app
    .\scripts\dev.ps1 -Browser   # backend + UI in your web browser (no Rust build needed)
#>
param(
    [switch]$Browser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
$backend = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$root\backend" `
    -FilePath "uv" -ArgumentList "run", "uninv-backend", "--reload"
$frontend = $null

try {
    if ($Browser) {
        Write-Host "Serving UI on http://127.0.0.1:1420 (Ctrl+C to stop) ..." -ForegroundColor Cyan
        $frontend = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$root\backend" `
            -FilePath "uv" -ArgumentList "run", "python", "-m", "http.server", "1420", "--bind", "127.0.0.1", "-d", "..\desktop\src"
        Start-Sleep -Seconds 2
        Start-Process "http://127.0.0.1:1420"
        Wait-Process -Id $frontend.Id
    }
    else {
        Push-Location "$root\desktop\src-tauri"
        try {
            # Prefer the Tauri CLI (watches files, rebuilds); fall back to plain cargo.
            cargo tauri --version *> $null
            if ($LASTEXITCODE -eq 0) { cargo tauri dev } else { cargo run }
        }
        finally { Pop-Location }
    }
}
finally {
    Write-Host "Stopping ..." -ForegroundColor Cyan
    foreach ($p in @($backend, $frontend)) {
        # /T kills the whole process tree (uv -> python -> uvicorn reloader workers).
        if ($p -and -not $p.HasExited) { taskkill /PID $p.Id /T /F *> $null }
    }
}
