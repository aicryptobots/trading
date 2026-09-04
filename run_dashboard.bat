@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python not found. Install Python 3.10+ and try again.&pause&exit /b 1)
python -m pip install -r requirements.txt
if errorlevel 1 (echo Dependency installation failed.&pause&exit /b 1)
echo.
echo Starting XAUUSDm Trading Dashboard...
echo Open http://127.0.0.1:5000
start "" http://127.0.0.1:5000
python app.py
pause
