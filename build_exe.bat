@echo off
REM ============================================================
REM  FAERS Mini Signal - Build Windows exe
REM  Usage: build_exe.bat
REM ============================================================

echo ============================================
echo  FAERS Mini Signal - Build Script
echo ============================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+.
    pause
    exit /b 1
)

REM Install/upgrade PyInstaller
echo [1/3] Installing PyInstaller...
pip install pyinstaller
echo.

REM Install project dependencies
echo [2/3] Installing project dependencies...
pip install -e .[dev]
echo.

REM Build
echo [3/3] Building executable...
pyinstaller faers_signal.spec --noconfirm
echo.

if exist "dist\FaersMiniSignal\FaersMiniSignal.exe" (
    echo ============================================
    echo  Build successful!
    echo  Output: dist\FaersMiniSignal\
    echo  Run:    dist\FaersMiniSignal\FaersMiniSignal.exe
    echo ============================================
) else (
    echo ============================================
    echo  Build FAILED. Check output above.
    echo ============================================
)

pause
