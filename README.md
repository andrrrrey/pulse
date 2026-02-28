# PULSE — Боевой Хаб

Тактическая операционная панель для координации командной работы в реальном времени. Предоставляет удобный интерфейс для управления картой, частотами, чатом, статистикой пилотов и отчётами об инцидентах.

---

## Содержание

- [Описание](#описание)
- [Функционал](#функционал)
- [Технологии](#технологии)
- [Структура проекта](#структура-проекта)
- [Запуск локально](#запуск-локально)
- [Развёртывание на VPS](#развёртывание-на-vps)
- [API](#api)

---

## Описание

**PULSE** — это легковесный full-stack веб-дашборд для тактических операций. Интерфейс выполнен в стиле киберпанк с оранжевыми акцентами и стеклянными элементами (glassmorphism). Бэкенд реализован на FastAPI + SQLite, фронтенд — чистый HTML/CSS/JS без фреймворков с интеграцией карт Leaflet.js.

Приложение запускается одной командой без сборки и работает сразу после старта.

---

## Функционал

### Карта (70% экрана)
- Интерактивная карта на базе **Leaflet.js** со спутниковым слоем Google
- Создание, редактирование и удаление тактических маркеров
- Типы маркеров: позиция, техника, дрон, РЭБ
- Цветовая маркировка: красный / оранжевый / голубой / фиолетовый
- Поля: координаты (lat/lng), название, приоритет, зона, доп. информация
- Поддержка системы координат **СК-42** с конвертацией
- Инструмент измерения расстояний (линейка)

### Управление частотами (правая панель, верх)
- Таблица радиочастот/каналов с цветовыми статусами:
  - **Зелёный** — свободна
  - **Оранжевый** — занята
  - **Красный** — перегружена
- Резервирование и снятие блокировки по двойному клику

### Чат и Килфид (правая панель, низ)
- Оперативный чат с ролями: свой / командир / другие операторы
- Временные метки всех сообщений
- Килфид — лента поражений с позывными, типом цели, координатами и примечаниями

### Таблица пилотов / Лидерборд
- Ростер пилотов с позывными и подразделениями
- Статистика по категориям: `tech`, `infantry`, `comms`, `agro`, `delivery`, `fpv`, `wing`, `queue`, `flights`
- Периоды: неделя / месяц / всё время
- Сортировка и фильтрация

### Система отчётов
- Форма репорта: заголовок, категория, приоритет, описание, шаги воспроизведения
- Поля: позывной, контакт, системная информация
- Прикрепление файлов (изображения/видео до **25 МБ**)
- Drag-and-drop загрузка файлов

### Настройки
- Хранение конфигурации приложения в БД (key-value)

---

## Технологии

| Слой | Технология |
|------|-----------|
| Backend | Python 3.x, FastAPI, SQLite 3 |
| ASGI-сервер | Uvicorn |
| Async файлы | aiofiles |
| Frontend | Vanilla JS, HTML5, CSS3 |
| Карты | Leaflet.js 1.9.4 |
| Шрифт | JetBrains Mono (Google Fonts CDN) |
| База данных | SQLite (автосоздание при старте) |

---

## Структура проекта

```
pulse/
├── server.py          # FastAPI бэкенд — все 21 API эндпоинт
├── database.py        # Инициализация и подключение к SQLite
├── main.html          # Основной SPA-фронтенд (HTML/CSS/JS)
├── static/
│   └── index.html     # Статический фронтенд (раздаётся на /)
├── uploads/           # Папка для загруженных файлов (создаётся автоматически)
└── pulse.db           # База данных SQLite (создаётся автоматически)
```

### Таблицы базы данных

| Таблица | Описание |
|---------|---------|
| `markers` | Маркеры на карте |
| `freq_state` | Состояния радиочастот |
| `chat_messages` | Сообщения оперативного чата |
| `bug_reports` | Отчёты об инцидентах |
| `settings` | Настройки приложения |
| `pilots` | Профили пилотов |
| `pilot_stats` | Статистика пилотов по периодам |
| `killfeed` | Лента поражений |

---

## Запуск локально

### Требования

- Python 3.9+

### Быстрый запуск (одна команда)

После клонирования репозитория — просто запустите лаунчер:

**Mac / Linux:**
```bash
git clone <url-репозитория> && cd pulse
./start.sh
```

**Windows:**
```bat
git clone <url-репозитория> && cd pulse
start.bat
```

**Универсально (любая платформа):**
```bash
python start.py
```

Лаунчер автоматически:
1. Создаст виртуальное окружение `venv/`
2. Установит все зависимости из `requirements.txt`
3. Запустит сервер на **http://localhost:8000**
4. Откроет браузер

После запуска откройте браузер: **http://localhost:8000**

База данных `pulse.db` и папка `uploads/` создадутся автоматически при первом старте.

#### Опции лаунчера

```bash
python start.py --port 9000        # другой порт
python start.py --no-browser       # не открывать браузер автоматически
python start.py --no-reload        # без автоперезагрузки при изменении файлов
```

### Остановка сервера

Если терминал был закрыт или сервер запущен в фоне:

```bash
# Через лаунчер (из папки проекта):
python start.py --stop

# Mac / Linux — напрямую через терминал:
lsof -ti :8000 | xargs kill

# Windows — напрямую через терминал:
for /f "tokens=5" %p in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %p
```

### Ручная установка (альтернатива)

```bash
# 1. Клонировать репозиторий
git clone <url-репозитория>
cd pulse

# 2. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate       # Linux/macOS
# venv\Scripts\activate        # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Запустить сервер
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

---

## Развёртывание на VPS

### 1. Подготовка сервера

```bash
# Обновить пакеты
sudo apt update && sudo apt upgrade -y

# Установить Python и pip
sudo apt install python3 python3-pip python3-venv -y

# Создать директорию приложения
mkdir -p /opt/pulse
cd /opt/pulse
```

### 2. Загрузка кода

```bash
# Вариант 1: через Git
git clone <url-репозитория> .

# Вариант 2: через scp с локальной машины
scp -r ./pulse user@your-server-ip:/opt/pulse
```

### 3. Установка зависимостей

```bash
cd /opt/pulse
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn aiofiles
```

### 4. Настройка systemd-сервиса (автозапуск)

Создать файл сервиса:

```bash
sudo nano /etc/systemd/system/pulse.service
```

Содержимое:

```ini
[Unit]
Description=PULSE Combat Hub
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/pulse
ExecStart=/opt/pulse/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Активировать и запустить:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pulse
sudo systemctl start pulse
sudo systemctl status pulse
```

### 5. Настройка Nginx (реверс-прокси)

```bash
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/pulse
```

Конфигурация:

```nginx
server {
    listen 80;
    server_name your-domain.com;   # или IP сервера

    client_max_body_size 30M;      # для загрузки файлов до 25 МБ

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
    }

    location /uploads/ {
        alias /opt/pulse/uploads/;
    }
}
```

Включить конфиг:

```bash
sudo ln -s /etc/nginx/sites-available/pulse /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6. SSL-сертификат (опционально, для HTTPS)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

### 7. Права на директорию

```bash
sudo chown -R www-data:www-data /opt/pulse
sudo chmod -R 755 /opt/pulse
```

После этого PULSE доступен по адресу **http://your-domain.com** (или **https://** при наличии SSL).

---

## API

Документация Swagger доступна по адресу: `http://localhost:8000/docs`

| Метод | Путь | Описание |
|-------|------|---------|
| `GET` | `/api/markers` | Список маркеров |
| `POST` | `/api/markers` | Создать маркер |
| `PATCH` | `/api/markers/{id}` | Обновить маркер |
| `DELETE` | `/api/markers/{id}` | Удалить маркер |
| `GET` | `/api/freq` | Состояния частот |
| `PUT` | `/api/freq` | Обновить частоты |
| `GET` | `/api/chat` | История чата |
| `POST` | `/api/chat` | Отправить сообщение |
| `GET` | `/api/killfeed` | Лента поражений |
| `POST` | `/api/killfeed` | Добавить запись |
| `GET` | `/api/pilots` | Список пилотов со статистикой |
| `POST` | `/api/pilots` | Добавить пилота |
| `PUT` | `/api/pilots/{id}/stats` | Установить статистику |
| `PATCH` | `/api/pilots/{id}/stats` | Инкрементировать статистику |
| `DELETE` | `/api/pilots/{id}` | Удалить пилота |
| `GET` | `/api/reports` | Список отчётов |
| `POST` | `/api/reports` | Создать отчёт |
| `POST` | `/api/uploads` | Загрузить файл (макс. 25 МБ) |
| `GET` | `/api/settings` | Получить настройки |
| `PUT` | `/api/settings` | Обновить настройки |
