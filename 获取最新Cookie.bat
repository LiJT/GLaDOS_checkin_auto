@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在打开已登录的浏览器，读取最新 Cookie 并写入 GitHub...
python sync_cookie.py
echo.
if errorlevel 1 (
  echo 没有完成。若弹出的浏览器还停在登录页，请登录后再双击一次这个文件。
) else (
  echo 已获取最新 Cookie，并写入 GitHub Actions。
)
echo.
pause
