@echo off
set PYTHON_PATH="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if exist %PYTHON_PATH% (
    start "" %PYTHON_PATH% "%~dp0main.py"
) else (
    start "" python "%~dp0main.py"
)
