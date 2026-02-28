#!/bin/bash
# PULSE — запуск на Mac / Linux
# Использование: ./start.sh [--port 9000] [--no-browser] [--no-reload]
cd "$(dirname "$0")"
python3 start.py "$@"
