@echo off
chcp 65001 >nul
title Barto Router - Inferencia Distribuida (Puerto 9000)
cd /d "%~dp0"
echo ===================================================
echo  Iniciando barto-router (127.0.0.1:9000/v1)...
echo  Proteccion activa de Unity y derivacion a GT 1030
echo ===================================================
python router.py
pause
