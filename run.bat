@echo off
title AudioX - Telegram Music, Video & Round Bot
echo ======================================================
echo           AudioX Bot Ishga Tushirilmoqda...
echo ======================================================

set PY_EXE=""

where py >nul 2>nul
if %errorlevel% equ 0 (
    set PY_EXE=py
    goto run
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set PY_EXE=python
    goto run
)

if exist "C:\Users\USER\AppData\Local\Programs\Python\Python314\python.exe" (
    set PY_EXE="C:\Users\USER\AppData\Local\Programs\Python\Python314\python.exe"
    goto run
)

echo [XATOLIK] Python topilmadi! Iltimos, Python o'rnatilganligini tekshiring.
pause
exit /b 1

:run
echo Python ishlatilmoqda: %PY_EXE%
%PY_EXE% main.py
if errorlevel 1 (
    echo.
    echo [OGOHLANTIRISH] Bot to'xtadi yoki xatolik yuz berdi.
    pause
)
