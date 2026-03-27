@echo off
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo.
echo ========================================
echo  LUNCHEROO - Starting Server
echo ========================================
echo.
echo Server: http://127.0.0.1:5000
echo Press Ctrl+C to stop
echo.
echo ========================================
echo.

python run.py

