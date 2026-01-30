@echo off
echo ========================================
echo Setup MetaTFT Auto-Sync Scheduled Task
echo ========================================
echo.
echo This will create a Windows scheduled task that runs
echo the sync script every time you log in.
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Please run this script as Administrator.
    pause
    exit /b 1
)

REM Get the script directory
set SCRIPT_DIR=%~dp0

REM Create the scheduled task
schtasks /create /tn "MetaTFT Auto-Sync" /tr "python \"%SCRIPT_DIR%sync_metatft.py\"" /sc onlogon /rl highest /f

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS! Auto-sync task created.
    echo The sync will run automatically when you log in.
    echo.
    echo To run manually: double-click sync_metatft.bat
    echo To remove task: schtasks /delete /tn "MetaTFT Auto-Sync" /f
) else (
    echo.
    echo Failed to create scheduled task.
)

pause
