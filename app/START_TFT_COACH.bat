@echo off
setlocal EnableDelayedExpansion

title TFT Coach Companion - Launcher
color 0A

echo.
echo  ========================================
echo       TFT COACH COMPANION LAUNCHER
echo  ========================================
echo.

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
cd /d "%ROOT_DIR%"

:: ============================================
:: CHECK DEPENDENCIES
:: ============================================

echo [1/5] Checking dependencies...

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found!
    echo  Please install Python from https://python.org
    echo  Make sure to check "Add Python to PATH" during install
    echo.
    pause
    exit /b 1
)

:: Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Node.js not found!
    echo  Please install Node.js from https://nodejs.org
    echo.
    pause
    exit /b 1
)

echo       Python: OK
echo       Node.js: OK

:: ============================================
:: INSTALL PYTHON DEPENDENCIES
:: ============================================

echo.
echo [2/5] Installing Python packages...

pip install fastapi uvicorn pandas numpy scikit-learn --quiet 2>nul
if %errorlevel% neq 0 (
    echo       Warning: Some packages may have failed, continuing...
) else (
    echo       Python packages: OK
)

:: ============================================
:: INSTALL NODE DEPENDENCIES
:: ============================================

echo.
echo [3/5] Installing frontend packages...

cd "%ROOT_DIR%\app\frontend"
if not exist "node_modules" (
    echo       Running npm install (this may take a minute)...
    npm install --silent 2>nul
)
echo       Frontend packages: OK

:: ============================================
:: START BACKEND SERVER
:: ============================================

echo.
echo [4/5] Starting backend server...

cd /d "%ROOT_DIR%"
start /B "TFT-Backend" cmd /c "python -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 2>nul"

:: Wait for backend to start
timeout /t 3 /nobreak >nul
echo       Backend: http://127.0.0.1:8000

:: ============================================
:: START FRONTEND SERVER
:: ============================================

echo.
echo [5/5] Starting frontend server...

cd "%ROOT_DIR%\app\frontend"
start /B "TFT-Frontend" cmd /c "npm run dev 2>nul"

:: Wait for frontend to start
timeout /t 3 /nobreak >nul
echo       Frontend: http://localhost:5173

:: ============================================
:: OPEN BROWSER
:: ============================================

echo.
echo  ========================================
echo       LAUNCHING TFT COACH COMPANION
echo  ========================================
echo.

timeout /t 2 /nobreak >nul
start "" "http://localhost:5173"

echo  App is running! Opening browser...
echo.
echo  Press any key to STOP the servers and exit.
echo.

pause >nul

:: ============================================
:: CLEANUP
:: ============================================

echo.
echo  Shutting down servers...

taskkill /F /FI "WINDOWTITLE eq TFT-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq TFT-Frontend*" >nul 2>&1
taskkill /F /IM "node.exe" /FI "WINDOWTITLE eq TFT*" >nul 2>&1

echo  Goodbye!
timeout /t 2 /nobreak >nul
