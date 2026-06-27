@echo off
chcp 65001 >nul
title AI Web Scraper

echo.
echo ============================================================
echo     AI 全自动网页抓取与可视化分析看板
echo ============================================================
echo.

pip show streamlit >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 未检测到 streamlit，正在安装依赖...
    echo.
    pip install -r requirements.txt
    echo.
    echo [完成] 依赖安装完毕！
    echo.
)

echo [启动] 正在启动 Streamlit 应用...
echo [提示] 浏览器将自动打开 http://localhost:8501
echo [提示] 关闭此窗口即可停止服务
echo.

streamlit run app.py --server.port 8501

pause
