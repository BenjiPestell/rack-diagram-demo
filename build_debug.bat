@echo off
REM Debug build — console window stays open so you can see startup errors

set PYTHON=python3
set PIP=python3 -m pip
set PYINSTALLER=python3 -m PyInstaller

echo Checking Python version...
%PYTHON% --version
if errorlevel 1 (
    echo ERROR: python3 not found.
    pause
    exit /b 1
)

%PIP% install pyinstaller flask qrcode pillow pyyaml --quiet

echo.
echo Building debug exe...
%PYINSTALLER% RackDesigner_debug.spec --clean --noconfirm

echo.
if exist dist\RackDesigner_debug.exe (
    echo Debug build ready. Running now...
    echo.
    dist\RackDesigner_debug.exe
) else (
    echo BUILD FAILED.
)
pause