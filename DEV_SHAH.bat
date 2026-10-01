@echo off
REM Development entry point: FastAPI with reload plus the Vite dev server.
setlocal
set "SHAH_ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SHAH_ROOT%scripts\start.ps1" -Dev %*
set "SHAH_EXIT=%ERRORLEVEL%"
if not "%SHAH_EXIT%"=="0" (
  echo.
  echo SHAH exited with code %SHAH_EXIT%.
  echo Run scripts\doctor.ps1 to diagnose, or scripts\setup.ps1 if this is a new checkout.
  echo.
  pause
)
endlocal & exit /b %SHAH_EXIT%
