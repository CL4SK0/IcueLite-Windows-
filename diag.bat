@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1 && (py -3 -m icuelite diag) || (python -m icuelite diag)
echo.
echo Envoie le fichier icuelite-diag.txt (dans ce dossier) si quelque chose ne marche pas.
pause
