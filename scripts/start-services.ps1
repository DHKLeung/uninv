<#
.SYNOPSIS
    Starts the uninv FastAPI backend in headless mode on Windows.
    Stops cleanly when Ctrl+C is pressed.
#>
$devScript = Join-Path $PSScriptRoot "dev.ps1"
& $devScript -ServicesOnly
