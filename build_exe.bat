@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   BUILD GAME SOUL SURVIVORS -^> FILE EXE
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [X] Khong tim thay Python. Hay cai Python tai https://www.python.org/downloads/
    echo     Nho tich chon "Add python.exe to PATH" khi cai dat.
    pause
    exit /b 1
)

python build_exe.py
if errorlevel 1 (
    echo.
    echo [X] Build that bai. Xem thong bao loi o tren.
) else (
    echo.
    echo [OK] File exe nam trong thu muc: dist\SoulSurvivors.exe
    start "" "%~dp0dist"
)
echo.
pause
