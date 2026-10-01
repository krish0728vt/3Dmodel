@echo off
REM Double-click entry point for the SHAH INDUSTRIES workspace.
REM Resolves the repository from this file's own location, so the copy can live
REM anywhere; no absolute paths are baked in.
setlocal
set "SHAH_ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SHAH_ROOT%scripts\start.ps1" %*
set "SHAH_EXIT=%ERRORLEVEL%"
if not "%SHAH_EXIT%"=="0" (
  echo.
  echo SHAH exited with code %SHAH_EXIT%.
  echo Run scripts\doctor.ps1 to diagnose, or scripts\setup.ps1 if this is a new checkout.
  echo.
  pause
)
endlocal & exit /b %SHAH_EXIT%
