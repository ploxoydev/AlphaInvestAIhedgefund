@echo off
chcp 65001 >nul
title TradingAgents - Multi-Agent LLM Trading Framework

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║          TradingAgents v0.2.5 - Tauric Research          ║
echo  ║       Multi-Agent LLM Financial Trading Framework        ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM Activate virtual environment
call "%~dp0venv\Scripts\activate.bat"

REM Load .env file if it exists
if exist "%~dp0.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0.env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" (
            set "%%A=%%B"
        )
    )
)

echo  Starting TradingAgents CLI...
echo.

python -m cli.main

echo.
echo  Session ended. Press any key to close.
pause >nul
