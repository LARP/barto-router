@echo off
chcp 65001 >nul
title Buscador Semantico RAG - barto-router
cd /d "%~dp0"

if "%~1"=="" (
    set /p "QUERY=Escribe tu consulta sobre el codigo/proyecto: "
) else (
    set "QUERY=%*"
)

python semantic_search.py "%QUERY%"
echo.
pause
