@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0play.ps1"
if errorlevel 1 (
    echo.
    echo Something went wrong - see the messages above.
    pause
)
