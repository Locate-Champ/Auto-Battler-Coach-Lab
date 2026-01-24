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

echo  Working directory: %ROOT_DIR%
echo.

:: ============================================
:: CHECK DEPENDENCIES
:: ============================================

echo [1/5] Checking dependencies...

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found!
    echo  Please install Python from https://python.org
    echo  Make sure to check "Add Python to PATH" during install
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo       %%i: OK

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Node.js not found!
    echo  Please install Node.js from https://nodejs.org
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo       Node.js %%i: OK

:: ============================================
:: INSTALL PYTHON DEPENDENCIES
:: ============================================

echo.
echo [2/5] Installing Python packages...
echo       (fastapi, uvicorn, pandas, numpy, scikit-learn)

pip install fastapi uvicorn pandas numpy scikit-learn --quiet
echo       Python packages: OK

:: ============================================
:: INSTALL NODE DEPENDENCIES
:: ============================================

echo.
echo [3/5] Installing frontend packages...

cd /d "%ROOT_DIR%\app\frontend"
if not exist "node_modules" (
    echo       Running npm install (this may take a minute)...
    call npm install
) else (
    echo       node_modules exists, skipping install
)
echo       Frontend packages: OK

:: ============================================
:: START BACKEND SERVER (visible window)
:: ============================================

echo.
echo [4/5] Starting backend server...

cd /d "%ROOT_DIR%"
start "TFT Coach - Backend" cmd /k "cd /d "%ROOT_DIR%" && python -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000"

:: Wait for backend to initialize
echo       Waiting for backend to start...
timeout /t 5 /nobreak >nul
echo       Backend: http://127.0.0.1:8000

:: ============================================
:: START FRONTEND SERVER (visible window)
:: ============================================

echo.
echo [5/5] Starting frontend server...

cd /d "%ROOT_DIR%\app\frontend"
start "TFT Coach - Frontend" cmd /k "cd /d "%ROOT_DIR%\app\frontend" && npm run dev"

:: Wait for frontend to start
echo       Waiting for frontend to start...
timeout /t 5 /nobreak >nul
echo       Frontend: http://localhost:5173

:: ============================================
:: OPEN BROWSER
:: ============================================

echo.
echo  ========================================
echo       TFT COACH IS RUNNING!
echo  ========================================
echo.
echo  Two new windows opened:
echo    - Backend (Python/FastAPI)
echo    - Frontend (Node/Vite)
echo.
echo  Opening browser in 3 seconds...

timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo  ----------------------------------------
echo  To stop: Close the Backend and Frontend
echo  command prompt windows, then press any
echo  key here to exit.
echo  ----------------------------------------
echo.

pause
