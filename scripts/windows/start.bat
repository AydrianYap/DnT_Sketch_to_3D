@echo off
rem D&T Sketch-to-3D launcher. Use the Start-*.bat files in the main folder instead of this one.
rem Usage: start.bat demo-or-ai local-or-lan
setlocal
cd /d "%~dp0\..\.."

if not exist "venv\Scripts\python.exe" (
    echo.
    echo [ERROR] The app is not installed yet: the folder "venv" is missing.
    echo Follow docs\WINDOWS_CPU_SETUP.md, Step 4 - Install.
    echo.
    pause
    exit /b 1
)

set "MODE=%~1"
set "WHERE=%~2"
if "%DNT_PORT%"=="" set "DNT_PORT=8000"

set "DNT_DEV_MODE="
set "MODE_TEXT=AI mode - TripoSR on the CPU"
set "PIXFORM_DEVICE=cpu"
set "PIXFORM_ACTIVE_MODELS=triposr"
if /I "%MODE%"=="demo" set "DNT_DEV_MODE=1"
if /I "%MODE%"=="demo" set "MODE_TEXT=DEMO mode - sample models, no AI"

set "DNT_HOST=127.0.0.1"
if /I "%WHERE%"=="lan" set "DNT_HOST=0.0.0.0"

echo.
echo  ============================================================
echo   D^&T Sketch-to-3D  -  %MODE_TEXT%
echo  ============================================================
if /I "%WHERE%"=="lan" echo   iPad testing: the web address and ACCESS CODE appear below.
if /I "%WHERE%"=="lan" echo   Keep this window open while you test.
if /I not "%WHERE%"=="lan" echo   Your browser will open http://localhost:%DNT_PORT%
echo   To STOP the app: click this window and press Ctrl+C,
echo   then answer Y if asked "Terminate batch job". Or close the window.
echo  ============================================================
echo.

if /I not "%WHERE%"=="lan" start "" /min cmd /c "timeout /t 8 /nobreak >nul & start http://localhost:%DNT_PORT%/"

"venv\Scripts\python.exe" "backend\app.py"

echo.
echo The server has stopped.
pause
