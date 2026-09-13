@echo off
chcp 65001 >nul
title Chat IA Local - barto-router / GT 1030

:: Navegar al directorio del script
cd /d "%~dp0"

:: Comprobar que Python est?? instalado y en el PATH
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] No se encontro Python en el PATH del sistema.
    echo Por favor instala Python o agregalo a las variables de entorno.
    pause
    exit /b 1
)

:: Ejecutar el chat interactivo
python chat.py %*

if %errorlevel% neq 0 (
    echo.
    echo [!] La sesion termino con un codigo de error.
    pause
)
