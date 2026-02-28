@echo off
:: PULSE — запуск на Windows
:: Использование: start.bat [--port 9000] [--no-browser] [--no-reload]
cd /d "%~dp0"
python start.py %*
