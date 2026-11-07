<#
.SYNOPSIS
    Starts the Interactive Brokers Client Portal Gateway.
.DESCRIPTION
    Launches the IBKR Web API gateway from gateways/ibkr-gateway.
    Once started, navigate to https://localhost:5000 in your browser to log in with 2FA.
#>
param()

# Ensure Java is on PATH (refreshes environment if installed recently)
$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath;$env:Path"

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    $foundJava = Get-ChildItem "C:\Program Files\Microsoft" -Recurse -Filter "java.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($foundJava) {
        $javaBin = Split-Path $foundJava.FullName
        $env:Path = "$javaBin;$env:Path"
        $env:JAVA_HOME = Split-Path $javaBin
    }
}

$GatewayDir = Join-Path $PSScriptRoot "..\gateways\ibkr-gateway"
if (-not (Test-Path $GatewayDir)) {
    Write-Error "IBKR Gateway directory not found at: $GatewayDir"
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting IBKR Client Portal Gateway" -ForegroundColor Cyan
Write-Host "  URL: https://localhost:5000" -ForegroundColor Cyan
Write-Host "  Keep this window open while using uninv with IBKR." -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

Push-Location $GatewayDir
try {
    & ".\bin\run.bat" "root\conf.yaml"
} finally {
    Pop-Location
}
