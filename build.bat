@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM  RackDesigner build script
REM  Run from the project root (the folder containing server.py)
REM ─────────────────────────────────────────────────────────────────────────

REM Use python3 explicitly to avoid picking up Inkscape's Python
set PYTHON=python3
set PIP=python3 -m pip
set PYINSTALLER=python3 -m PyInstaller

echo Checking Python version...
%PYTHON% --version
if errorlevel 1 (
    echo ERROR: python3 not found. Make sure Python 3 is on your PATH as "python3".
    pause
    exit /b 1
)

echo.
echo Installing / upgrading build dependencies...
%PIP% install pyinstaller flask qrcode pillow pyyaml --quiet

echo.
echo Building React frontend...
pushd frontend
call npm install --silent
call npm run build
popd
if not exist frontend_dist\index.html (
    echo ERROR: React build failed - frontend_dist\index.html not found.
    pause
    exit /b 1
)

echo.
echo Building RackDesigner.exe...
%PYINSTALLER% RackDesigner.spec --clean --noconfirm

echo.
if exist dist\RackDesigner.exe (
    echo  SUCCESS: dist\RackDesigner.exe is ready.
    echo.
    echo  To distribute to a colleague:
    echo    1. Copy dist\RackDesigner.exe to any folder
    echo    2. Optionally place a system.yaml next to it
    echo       ^(or let it create a blank one on first run^)
    echo    3. Double-click RackDesigner.exe -- no Python needed
    echo    4. output\ and pngs\ folders are created automatically
    echo.
    echo  Note: Graphviz ^(dot.exe^) must be installed on the target machine
    echo  for PNG diagram generation.  https://graphviz.org/download/
) else (
    echo  BUILD FAILED. Check the output above for errors.
)
echo.
pause