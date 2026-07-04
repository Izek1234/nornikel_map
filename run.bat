@echo off
echo ===== NORNIKEL Knowledge Map =====
echo.

echo 1. Killing old processes...
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
timeout /t 2 >nul

echo 2. Starting Backend (uvicorn) on port 8000...
start "Backend" cmd /c "cd /d %~dp0backend & .venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 > %~dp0backend.log 2>&1"
echo    Backend starting... Check backend.log for status

echo 3. Starting Frontend (npm run dev) on port 3000...
start "Frontend" cmd /c "cd /d %~dp0frontend & npm.cmd run dev > %~dp0frontend.log 2>&1"
echo    Frontend starting... Check frontend.log for status

echo.
echo 4. Waiting for servers...
timeout /t 5 >nul

echo.
echo ===== Status =====
echo Backend:  http://localhost:8000/health
echo Frontend: http://localhost:3000
echo.
echo Logs: backend.log / frontend.log
echo To stop: taskkill /f /im uvicorn.exe ^&^& taskkill /f /im node.exe
