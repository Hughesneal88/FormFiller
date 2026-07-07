@echo off
cd /d "%~dp0"
echo Installing Python dependencies...
py -m pip install -r requirements.txt
echo.
echo Installing Playwright browsers...
py -m playwright install chromium
echo.
echo Starting Survey Auto-Filler...
echo Open http://localhost:8000 in your browser
echo.
py -m app.main --host 0.0.0.0 --port 8000
