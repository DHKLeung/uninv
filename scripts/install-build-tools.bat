@echo off
echo ===================================================
echo Installing Visual Studio 2022 C++ Build Tools
echo ===================================================
echo.
winget install Microsoft.VisualStudio.2022.BuildTools --override "--passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
pause
