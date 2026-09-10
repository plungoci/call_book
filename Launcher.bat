@echo off
rem Porneste lansatorul cu Python-ul din mediul virtual local, daca exista.
setlocal
set "PROJECT_DIR=%~dp0"
if exist "%PROJECT_DIR%.venv\Scripts\python.exe" (
    "%PROJECT_DIR%.venv\Scripts\python.exe" "%PROJECT_DIR%launcher.py"
) else (
    python "%PROJECT_DIR%launcher.py"
)
