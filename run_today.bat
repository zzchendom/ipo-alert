@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 优先使用环境变量 IPO_ALERT_PYTHON, 否则尝试 PATH 中的 pythonw / python
if defined IPO_ALERT_PYTHON (
    "%IPO_ALERT_PYTHON%" main.py --force
) else (
    where pythonw.exe >nul 2>&1 && (pythonw main.py --force) || python main.py --force
)
