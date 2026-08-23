@echo off
title MeshForge 3D — Universal 3D Studio
cd /d "%~dp0"

echo ============================================================
echo   MeshForge 3D — Universal Image to 3D AI Studio
echo ============================================================
echo Starting application in desktop window...
echo.

python app\main.py --window

if errorlevel 1 (
    echo.
    echo [Notice] Trying standard python launcher...
    py -3.11 app\main.py --window || py app\main.py --window
)

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to launch MeshForge 3D.
    echo Please make sure Python with project dependencies is installed.
    pause
)
