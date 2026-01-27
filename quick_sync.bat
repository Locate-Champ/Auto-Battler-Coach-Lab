@echo off
REM Quick sync script - run from your Windows machine
REM Usage: quick_sync.bat [folder_name]
REM Example: quick_sync.bat jan-27-game2

set FOLDER=%1
if "%FOLDER%"=="" set FOLDER=live-logs

REM Copy MetaTFT logs to repo folder
set METATFT_LOGS=%localappdata%\Overwolf\Log\Apps\MetaTFT
set REPO_PATH=E:\VS Code\tft-coach-234\tft-coach-234

mkdir "%REPO_PATH%\%FOLDER%" 2>nul
copy "%METATFT_LOGS%\background.html.log" "%REPO_PATH%\%FOLDER%\"
copy "%METATFT_LOGS%\main.html.log" "%REPO_PATH%\%FOLDER%\"
copy "%METATFT_LOGS%\ingamedesktop.html.log" "%REPO_PATH%\%FOLDER%\"

REM Quick commit and push (no checks on feature branches)
cd /d "%REPO_PATH%"
git add "%FOLDER%\*"
git commit -m "Live logs: %FOLDER%"
git push

echo Done! Logs synced to %FOLDER%
