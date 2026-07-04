@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [Spy-Look] 启动后端 API ...
start "Spy-Look API" cmd /k "pushd "%~dp0api" && uv run python main.py"

echo [Spy-Look] 启动前端 UI ...
start "Spy-Look UI" cmd /k "pushd "%~dp0ui" && npm run dev"

echo.
echo 后端: http://127.0.0.1:8000
echo 前端: http://127.0.0.1:5173  （开发模式，API 代理到 8000）
echo.
echo 两个窗口已打开，关闭对应窗口即可停止服务。
pause
