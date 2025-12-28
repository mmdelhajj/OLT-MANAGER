@echo off
REM ============================================
REM OLT Manager - Windows Build Script
REM Run this on Windows with Python installed
REM ============================================

echo ========================================
echo   OLT Manager - Windows Build
echo ========================================

REM Check Python
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Install Python 3.10+ first.
    pause
    exit /b 1
)

REM Install requirements
echo [1/4] Installing dependencies...
pip install nuitka pyinstaller
pip install fastapi uvicorn sqlalchemy python-jose passlib bcrypt
pip install python-multipart pysnmp aiohttp requests paramiko boto3 jinja2 aiofiles

REM Create build folder
echo [2/4] Preparing build...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
mkdir dist

REM Compile with Nuitka
echo [3/4] Compiling with Nuitka (this takes 30-60 min)...
python -m nuitka --standalone --onefile --output-dir=dist --output-filename=olt-manager.exe --windows-console-mode=disable main.py

echo [4/4] Build complete!
echo.
echo ========================================
echo   BUILD COMPLETE!
echo ========================================
echo.
echo   Your Windows executable:
echo   dist\olt-manager.exe
echo.
echo ========================================
pause
