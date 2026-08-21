@echo off
cd /d "%~dp0"
python controller_fusion.py --gui
if errorlevel 1 (
    echo.
    echo Something went wrong - see the messages above.
    pause
)
