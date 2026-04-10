@echo off
setlocal
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" "%~dp0run_text_adventure.py" %*
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Could not find a Python interpreter. Install Python or create .venv.
        exit /b 1
    )
    python "%~dp0run_text_adventure.py" %*
)
