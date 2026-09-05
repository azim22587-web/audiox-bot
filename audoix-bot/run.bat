@echo off
title Audoix - Telegram Music & Media Bot
echo ======================================================
echo           Audoix Bot Ishga Tushirilmoqda...
echo ======================================================
py main.py
if errorlevel 1 (
    echo.
    echo Bot to'xtadi yoki xatolik yuz berdi.
    pause
)
