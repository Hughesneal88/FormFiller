@echo off
cd /d "%~dp0"
echo Installing Python dependencies...
pip install -r requirements.txt
echo.
echo Installing Playwright browsers...
playwright install chromium
echo.
echo Starting Survey Auto-Filler...
echo Open http://localhost:8000 in your browser
echo.
python -m app.main --host 0.0.0.0 --port 8000
