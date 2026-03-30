@echo off
cd /d "%~dp0"

echo ========================================
echo   LUA Story Generator
echo   HTTP: http://localhost:9000
echo   TCP:  tcp://127.0.0.1:9010
echo ========================================
echo.

if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:9000"

python main.py
if %ERRORLEVEL% GEQ 1 (
    echo.
    echo Start failed. Run: pip install -r requirements.txt
    pause
)
