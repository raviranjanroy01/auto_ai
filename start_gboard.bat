@echo off
REM ═══════════════════════════════════════════════════
REM  Desktop G-Board — Quick Start
REM ═══════════════════════════════════════════════════
REM  Launches the Desktop G-Board typing assistant.
REM  Uses the fallback (pynput) hook by default.
REM  Add --hook native after building the C++ service.
REM ═══════════════════════════════════════════════════

echo.
echo  ══════════════════════════════════════════
echo   Desktop G-Board v0.2.0
echo   Global AI Typing Assistant
echo  ══════════════════════════════════════════
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo  [OK] Virtual environment activated.
) else (
    echo  [!] No venv found. Using system Python.
)

echo  [..] Starting Desktop G-Board...
echo.

python main.py %*

pause
