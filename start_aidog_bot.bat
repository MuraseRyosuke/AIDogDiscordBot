@echo off
rem --- Set Window Title ---
title AI-Dog Bot Launcher

echo -------------------------------------
echo  AI-Dog Discord Bot Launcher
echo -------------------------------------
echo.

rem --- Change directory to the script's location ---
cd /d "%~dp0"
echo [INFO] Changed directory to: %CD%
echo.

rem --- Attempt to activate virtual environment (venv) ---
echo [INFO] Looking for virtual environment (venv)...
if exist "venv\Scripts\activate.bat" (
    echo [OK] venv found. Activating...
    call "venv\Scripts\activate.bat"
    echo.
) else (
    echo [WARN] venv not found. Using global Python installation.
    echo        If you face library errors, please run: pip install -r requirements.txt
    echo.
)

rem --- Run the Python script ---
echo [INFO] Starting AI-Dog Bot (bot_main.py)...
echo        (To stop the bot, press Ctrl+C in this console)
echo -------------------------------------
echo.

python bot_main.py

echo.
echo -------------------------------------
echo [INFO] The bot process has ended.
echo.
echo Please check the console window for any error messages.
echo Press any key to close this window...
pause