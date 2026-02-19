@echo off
echo ========================================
echo Auto-Battler Coach Companion
echo ========================================
echo.

REM Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found
    pause
    exit /b 1
)

REM Run the launcher
python "%~dp0run_app.py"

pause

