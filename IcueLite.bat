@echo off
rem Ouvre IcueLite sans fenetre console
cd /d "%~dp0"
where pyw >nul 2>&1 && (start "" pyw -3 IcueLite.pyw %*) || (start "" pythonw IcueLite.pyw %*)
