<#
.SYNOPSIS
    Starts all broker gateways and the FastAPI backend in headless service mode.
    Stops everything cleanly when Ctrl+C is pressed.
#>
$devScript = Join-Path $PSScriptRoot "dev.ps1"
& $devScript -ServicesOnly
