@echo off
REM Quick sync script - run from your Windows machine
REM Usage: quick_sync.bat [subfolder_name]
REM Example: quick_sync.bat jan-27-game2

set FOLDER=%1
if "%FOLDER%"=="" set FOLDER=live-logs

REM Copy MetaTFT logs to repo folder
set METATFT_LOGS=%localappdata%\Overwolf\Log\Apps\MetaTFT
set REPO_PATH=E:\VS Code\Auto-Battler-Coach-Lab
set TARGET_PATH=%REPO_PATH%\data\local\%FOLDER%

mkdir "%TARGET_PATH%" 2>nul
copy "%METATFT_LOGS%\background.html.log" "%TARGET_PATH%\"
copy "%METATFT_LOGS%\main.html.log" "%TARGET_PATH%\"
copy "%METATFT_LOGS%\ingamedesktop.html.log" "%TARGET_PATH%\"

echo Done! Logs synced to data\\local\\%FOLDER%
