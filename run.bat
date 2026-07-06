@echo off
set PLAYWRIGHT_BROWSERS_PATH=%CD%\browsers
echo ===================================================
echo   Survey Auto-Filler Application Installer & Runner
echo ===================================================
echo.

:: Check for python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

:: Install dependencies
echo Installing requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Install Playwright browser
echo Installing browser binaries for automation...
playwright install chromium
if %errorlevel% neq 0 (
    echo [WARNING] Playwright browser installation failed or returned warning.
    echo Attempting to proceed anyway...
)

echo.
echo ===================================================
echo   Starting server on http://localhost:8000
echo   Open your browser and navigate to this address.
echo ===================================================
echo.
python server.py

pause
