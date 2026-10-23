@echo off
chcp 65001 >nul
echo 正在启动后端服务...
cd /d "%~dp0backend"
call ..\..\venv\Scripts\activate.bat
python main.py
pause
