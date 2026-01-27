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

echo  Working directory: %CD%
echo.

:: ============================================
:: CHECK DEPENDENCIES
:: ============================================

echo [1/5] Checking dependencies...
echo.

:: Check Python
echo       Checking Python...
python --version 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found!
    echo  Please install Python from https://python.org
    echo  Make sure to check "Add Python to PATH" during install
    echo.
    pause
    exit /b 1
)
echo       Python: OK
echo.

:: Check Node.js
echo       Checking Node.js...
node --version 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Node.js not found!
    echo  Please install Node.js from https://nodejs.org
    echo.
    pause
    exit /b 1
)
echo       Node.js: OK
echo.

echo  Press any key to continue to package installation...
pause >nul

:: ============================================
:: INSTALL PYTHON DEPENDENCIES
:: ============================================

echo.
echo  ========================================
echo [2/5] Installing Python packages...
echo  ========================================
echo.

echo  Running: pip install fastapi uvicorn pandas numpy scikit-learn
echo.
pip install fastapi uvicorn pandas numpy scikit-learn
echo.

if %errorlevel% neq 0 (
    echo  WARNING: pip install had errors. Check above.
    echo.
) else (
    echo  Python packages: DONE
    echo.
)

echo  Press any key to continue to frontend installation...
pause >nul

:: ============================================
:: INSTALL NODE DEPENDENCIES
:: ============================================

echo.
echo  ========================================
echo [3/5] Installing frontend packages...
echo  ========================================
echo.

cd /d "%ROOT_DIR%\app\frontend"
echo  Current directory: %CD%
echo.

if not exist "node_modules" (
    echo  Running: npm install
    echo  (This may take 1-2 minutes on first run)
    echo.
    call npm install
    echo.
) else (
    echo  node_modules already exists, skipping npm install
    echo.
)

echo  Frontend packages: DONE
echo.

echo  Press any key to start the servers...
pause >nul

:: ============================================
:: START BACKEND SERVER
:: ============================================

echo.
echo  ========================================
echo [4/5] Starting backend server...
echo  ========================================
echo.

cd /d "%ROOT_DIR%"
echo  Current directory: %CD%
echo  Running: python -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000
echo.
echo  A NEW WINDOW will open for the backend server.
echo  Watch that window for any errors!
echo.

start "TFT Coach - Backend" cmd /k "cd /d %ROOT_DIR% && echo Starting backend... && echo. && python -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000"

echo  Waiting 8 seconds for backend to initialize...
timeout /t 8

echo.
echo  Backend should be running at: http://127.0.0.1:8000
echo.

echo  Press any key to start frontend...
pause >nul

:: ============================================
:: START FRONTEND SERVER
:: ============================================

echo.
echo  ========================================
echo [5/5] Starting frontend server...
echo  ========================================
echo.

cd /d "%ROOT_DIR%\app\frontend"
echo  Current directory: %CD%
echo  Running: npm run dev
echo.
echo  A NEW WINDOW will open for the frontend server.
echo  Watch that window for any errors!
echo.

start "TFT Coach - Frontend" cmd /k "cd /d %ROOT_DIR%\app\frontend && echo Starting frontend... && echo. && npm run dev"

echo  Waiting 5 seconds for frontend to start...
timeout /t 5

echo.
echo  Frontend should be running at: http://localhost:5173
echo.

:: ============================================
:: OPEN BROWSER
:: ============================================

echo.
echo  ========================================
echo       ALL SERVERS STARTED!
echo  ========================================
echo.
echo  Backend:  http://127.0.0.1:8000
echo  Frontend: http://localhost:5173
echo.
echo  Check the two server windows for any errors.
echo.
echo  Press any key to open browser...
pause >nul

start "" "http://localhost:5173"

echo.
echo  ========================================
echo  Browser opened! App should be loading.
echo  ========================================
echo.
echo  If you see "refused to connect":
echo    1. Check the Backend window for errors
echo    2. Check the Frontend window for errors
echo    3. Make sure ports 8000 and 5173 are free
echo.
echo  To STOP the app:
echo    Close the Backend and Frontend windows
echo.
echo  Press any key to exit this launcher...
pause >nul
