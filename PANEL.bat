@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul 2>&1
title MC Servers Panel

echo.
echo    ####   MC SERVERS PANEL   ####
echo.

if not exist "mcpanel\__main__.py" (
    echo    [X] Dossier "mcpanel" introuvable.
    echo        Ce fichier doit rester a cote du dossier mcpanel\ et de web\.
    echo.
    pause
    exit /b 1
)

:: --- recherche d'un Python 3 utilisable ---
set "PY="
where py.exe >nul 2>&1 && (
    py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    for %%P in (python.exe python3.exe) do (
        if not defined PY (
            where %%P >nul 2>&1 && (
                %%P -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1 && set "PY=%%P"
            )
        )
    )
)

if not defined PY (
    echo    [X] Python 3.9+ est requis et n'a pas ete trouve.
    echo.
    echo        Option 1 - automatique :
    echo          winget install -e --id Python.Python.3.12
    echo        Option 2 - manuelle :
    echo          https://www.python.org/downloads/   ^(cochez "Add python.exe to PATH"^)
    echo.
    where winget >nul 2>&1
    if !ERRORLEVEL!==0 (
        choice /C ON /N /M "    Installer Python maintenant avec winget ? [O/N] "
        if !ERRORLEVEL!==1 (
            echo.
            winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
            echo.
            echo    Installation terminee. Fermez cette fenetre et relancez PANEL.bat
        )
    )
    echo.
    pause
    exit /b 1
)

echo    Python OK. Demarrage du panel...
echo    Le navigateur s'ouvre tout seul sur http://localhost:8765/
echo    Laissez cette fenetre ouverte. Ctrl+C pour tout arreter.
echo.

%PY% -m mcpanel
set "RC=!ERRORLEVEL!"

if not "!RC!"=="0" (
    echo.
    echo    [X] Le panel s'est arrete avec le code !RC!.
    echo        Message d'erreur juste au-dessus.
    echo.
    pause
)
exit /b !RC!
