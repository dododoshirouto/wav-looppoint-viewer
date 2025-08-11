:: _build_win.bat
@echo off
setlocal enabledelayedexpansion

set APP_NAME=WavLoopInspector_win
set MAIN=_main.py

:: venv優先、無ければPATHのpython
set PY=venv\Scripts\python.exe
if not exist "%PY%" set PY=python

:: dist/ をクリーン（PyInstallerの--cleanも併用）
if exist "build" rmdir /s /q "build"
if exist "dist\%APP_NAME%.exe" del /q "dist\%APP_NAME%.exe"

"%PY%" -m pip install --upgrade pip >nul 2>&1
"%PY%" -m pip show pyinstaller >nul 2>&1 || "%PY%" -m pip install pyinstaller

"%PY%" -m PyInstaller --onefile --clean ^
  --name "%APP_NAME%" ^
  --icon "icon.ico" ^
  "%MAIN%"

if errorlevel 1 goto :fail

echo 成功: dist\%APP_NAME%.exe
goto :eof

:fail
echo 失敗しました（PyInstaller）。
exit /b 1
