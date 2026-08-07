@echo off
chcp 65001 >nul
echo ============================================
echo   会务助手 - Meeting Assistant
echo ============================================
echo.

cd /d "%~dp0"

echo [1/2] Starting backend server on port 10023...
start "FaceSupport-Backend" cmd /c "cd backend && python main.py"

echo [2/2] Starting frontend dev server...
cd frontend
call npm run dev

pause
