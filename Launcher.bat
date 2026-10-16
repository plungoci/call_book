@echo off
rem Porneste lansatorul cu Python-ul din mediul virtual local, daca exista.
rem Daca aplicatia nu porneste, fereastra ramane deschisa ca eroarea sa poata fi citita.
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launcher.py
) else (
    rem "py" este lansatorul oficial Python; "python" poate fi doar scurtatura
    rem catre Microsoft Store, care nu este un Python real.
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 launcher.py
    ) else (
        python launcher.py
    )
)
if errorlevel 1 (
    echo.
    echo Radio Logbook nu a putut porni. Citeste mesajele de mai sus.
    echo Daca lipseste ceva, ruleaza din nou scriptul de instalare din README.
    pause
)
exit /b %errorlevel%
