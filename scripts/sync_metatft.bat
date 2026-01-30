@echo off
echo ========================================
echo MetaTFT Auto-Sync
echo ========================================
echo.

REM Try to find Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python first.
    pause
    exit /b 1
)

REM Run the sync script
python "%~dp0sync_metatft.py" %*

echo.
pause
