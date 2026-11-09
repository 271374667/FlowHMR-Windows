@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "FLOWHMR_PY=.venv\Scripts\python.exe"
if exist "runtime\python.exe" set "FLOWHMR_PY=runtime\python.exe"
"%FLOWHMR_PY%" tools\windows\check_install.py %*
pause
