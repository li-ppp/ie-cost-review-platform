@echo off
chcp 65001 >nul
echo ========================================
echo IE工程造价审报自动生成平台 - 启动脚本
echo ========================================
echo.

:: 检查虚拟环境（venv 位于上级目录）
if not exist "..\venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先在上级目录创建 venv
    pause
    exit /b 1
)

:: 检查前端依赖
if not exist "frontend\node_modules" (
    echo [错误] 前端依赖未安装，请先运行 npm install
    pause
    exit /b 1
)

echo [1/2] 启动后端服务...
start "后端服务" cmd /k "cd /d "%~dp0" && call ..\venv\Scripts\activate.bat && cd backend && python main.py"

timeout /t 3 /nobreak >nul

echo [2/2] 启动前端服务...
start "前端服务" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================
echo 系统启动完成！
echo 后端地址: http://localhost:8000
echo 前端地址: http://localhost:5173
echo ========================================
echo.
echo 按任意键关闭此窗口（服务会继续运行）
pause >nul
