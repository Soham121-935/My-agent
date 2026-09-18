@echo off
setlocal
set APP_NAME=MATLAB-Simulink-AI-Agent

echo Building %APP_NAME%.exe
where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher ^(py^) was not found. Install Python 3.10+ from python.org and retry.
    exit /b 1
)

if not exist .venv\Scripts\python.exe (
    echo Creating a build environment...
    py -3 -m venv .venv
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1

python -m PyInstaller --noconfirm --clean --onefile --windowed --name "%APP_NAME%" --paths . app\main.py
if errorlevel 1 exit /b 1

echo.
echo Build complete: dist\%APP_NAME%.exe
endlocal
