@echo off
setlocal enabledelayedexpansion
echo ================================================
echo  LinBurn Windows Build - PyInstaller
echo ================================================
echo.

REM --- Move to repo root (two levels up from this script) ---
cd /d "%~dp0..\.."
echo Repo root: %CD%
echo.

REM --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ and add it to PATH.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo Found: %%v

REM --- Install / upgrade build dependencies ---
echo.
echo Installing build dependencies...
pip install --upgrade pyinstaller PyQt6 pillow
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause & exit /b 1
)

REM --- Convert PNG icon to ICO (Pillow) ---
echo.
echo Converting icon PNG to ICO...
python -c ^
  "from PIL import Image; ^
   img = Image.open('Assets/Gemini_Generated_Image_296qmr296qmr296q.png').convert('RGBA'); ^
   img.save('Assets/icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]); ^
   print('icon.ico created.')"
if errorlevel 1 (
    echo WARNING: Icon conversion failed - .exe will have no custom icon.
)

REM --- Clean previous build ---
echo.
echo Cleaning previous build artifacts...
if exist "dist\LinBurn.exe" del /q "dist\LinBurn.exe"
if exist "build\LinBurn"    rmdir /s /q "build\LinBurn"

REM --- Run PyInstaller ---
echo.
echo Building LinBurn.exe (single-file, UAC=admin)...
pyinstaller packaging\windows\linburn.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    pause & exit /b 1
)

echo.
echo ================================================
echo  Build successful!
echo  Output: dist\LinBurn.exe
echo ================================================
echo.
echo The .exe requires Windows 10/11 and runs as Administrator (UAC prompt).
pause
