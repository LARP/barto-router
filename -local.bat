@echo off
chcp 65001 >nul
python "%~dp0chat.py" -local %*
