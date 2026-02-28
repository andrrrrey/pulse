#!/usr/bin/env python3
"""
PULSE — универсальный лаунчер (Mac / Windows / Linux)

Запуск:
    python start.py          # или python3 start.py на Mac/Linux
    python start.py --port 9000   # кастомный порт
    python start.py --no-browser  # без автооткрытия браузера
"""

import sys
import os
import subprocess
import platform
import time
import threading
import webbrowser
import argparse

MIN_PYTHON = (3, 9)
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


def check_python_version():
    if sys.version_info < MIN_PYTHON:
        print(
            f"Ошибка: требуется Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ "
            f"(у вас {sys.version_info.major}.{sys.version_info.minor})"
        )
        sys.exit(1)


def get_venv_python(venv_dir):
    if platform.system() == "Windows":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def get_venv_pip(venv_dir):
    if platform.system() == "Windows":
        return os.path.join(venv_dir, "Scripts", "pip.exe")
    return os.path.join(venv_dir, "bin", "pip")


def setup_venv(project_dir):
    venv_dir = os.path.join(project_dir, "venv")
    if not os.path.exists(venv_dir):
        print("Создаю виртуальное окружение...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        print("Виртуальное окружение создано.\n")
    return venv_dir


def install_requirements(venv_dir, project_dir):
    pip = get_venv_pip(venv_dir)
    requirements = os.path.join(project_dir, "requirements.txt")
    print("Проверяю зависимости...")
    subprocess.check_call([pip, "install", "-q", "-r", requirements])
    print("Зависимости установлены.\n")


def open_browser_delayed(url, delay=2):
    def _open():
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def parse_args():
    parser = argparse.ArgumentParser(description="PULSE лаунчер")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Порт сервера (по умолчанию: 8000)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Хост сервера (по умолчанию: 0.0.0.0)")
    parser.add_argument("--no-browser", action="store_true", help="Не открывать браузер автоматически")
    parser.add_argument("--no-reload", action="store_true", help="Отключить автоперезагрузку при изменении файлов")
    return parser.parse_args()


def main():
    check_python_version()
    args = parse_args()

    project_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 50)
    print("  PULSE — Боевой Хаб")
    print("=" * 50)

    venv_dir = setup_venv(project_dir)
    install_requirements(venv_dir, project_dir)

    url = f"http://localhost:{args.port}"

    print(f"  Адрес: {url}")
    print(f"  Стоп:  Ctrl+C")
    print("=" * 50 + "\n")

    if not args.no_browser:
        open_browser_delayed(url)

    python = get_venv_python(venv_dir)
    cmd = [
        python, "-m", "uvicorn", "server:app",
        "--host", args.host,
        "--port", str(args.port),
    ]
    if not args.no_reload:
        cmd.append("--reload")

    try:
        subprocess.run(cmd, cwd=project_dir)
    except KeyboardInterrupt:
        print("\nСервер остановлен.")


if __name__ == "__main__":
    main()
