@echo off
rem Facultatif : fabrique dist\IcueLite.exe (plus besoin de Python ensuite)
cd /d "%~dp0"
where py >nul 2>&1 && (set PY=py -3) || (set PY=python)
%PY% -m pip install --user --upgrade pyinstaller -r requirements.txt
%PY% -c "from icuelite import logo; logo.save_ico('IcueLite.ico')"
%PY% -m PyInstaller --noconfirm --onefile --windowed --collect-data customtkinter --add-data "icuelite\assets;icuelite\assets" --icon IcueLite.ico --name IcueLite IcueLite.pyw
echo.
echo Fichier cree : %~dp0dist\IcueLite.exe
pause
