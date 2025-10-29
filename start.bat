@echo off
cd /d "%~dp0"
echo.
echo ========================================
echo  LUNCHEROO - REFACTORED VERSION
echo ========================================
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
    echo.
) else (
    echo Warning: Virtual environment not found at .venv
    echo Using system Python...
    echo.
)

echo Checking dependencies...
echo.

pip install -q -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo  Failed to install dependencies!
    echo ========================================
    echo.
    pause
    exit /b 1
)

echo.
echo Testing the refactored application...
echo.

python test_refactoring.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  Tests passed! Starting the server...
    echo ========================================
    echo.
    echo Server will start on: http://127.0.0.1:5000
    echo Frontend should connect to this URL
    echo.
    echo Press Ctrl+C to stop the server
    echo.

    python run.py
) else (
    echo.
    echo ========================================
    echo  Tests failed! Please check the errors above.
    echo ========================================
    echo.
    pause
)


