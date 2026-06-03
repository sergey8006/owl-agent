# OWL Agent v3.0 — Offline AI Agent Platform

Локальный AI-агент с мульти-агентной системой, Flow Engine, 16 скиллов,
веб-UI и полной автономностью. Работает полностью оффлайн
(кроме LLM-бэкенда).

## Возможности

### Агентная система
- **Tool calling** — агент может читать/писать файлы, запускать скрипты,
  искать по памяти, выполнять Python-код
- **Memory System** — SQLite с FTS5-поиском, тегами, дедупликацией.
  Агент помнит контекст между сессиями
- **Agent Teams** — мульти-агентное сотрудничество: несколько агентов
  работают над задачами параллельно
- **16 скиллов** — image-processor, data-analyzer, doc-reader,
  system-monitor, nodejs, project_manager и другие
- **AutoSkill** — агент автоматически создаёт новые скиллы
  из успешных решений

### Flow Engine
- Визуальный редактор процессов (если/иначе, циклы, параллельные ветки)
- Создание workflow без кода через веб-UI
- Шаблоны проектов с переменными

### Сервер
- Stdlib-сервер (без Flask, чистый Python)
- Flask-сервер с REST API
- Rate limiting, API key аутентификация, health endpoint
- CORS поддержка для внешних клиентов

### Веб-UI
- Чат с агентом
- Файловый менеджер
- Редактор скриптов
- Панель скиллов
- Визуальный Flow Editor
- Панель управления проектами

## Сравнение с другими AI-агентами

| Возможность | OWL Agent | AutoGPT | CrewAI | LangGraph |
|---|---|---|---|---|
| Работа оффлайн | Да | Нет | Нет | Нет |
| Веб-UI из коробки | Да | Нет | Нет | Нет |
| Мульти-агенты | Да | Нет | Да | Да |
| Flow Engine | Да | Нет | Нет | Да |
| Скиллы | 16 | Плагины | Tools | Tools |
| Память (FTS5) | Да | Ограничено | Нет | State |
| Python only | Да | Да | Да | Да |
| ~100MB RAM | Да | Нет (~1GB+) | Нет | Нет |

### Ключевые отличия

**vs AutoGPT** — OWL работает полностью оффлайн, не требует OpenAI API,
имеет встроенный веб-UI, потребляет значительно меньше ресурсов.

**vs CrewAI** — CrewAI — фреймворк для разработчиков, требует написания
кода. OWL — готовое приложение с графическим интерфейсом, Flow Editor
и оффлайн-установкой.

**vs LangGraph** — LangGraph — библиотека для построения графов агентов,
требует глубоких знаний Python. OWL — автономное приложение с визуальным
редактором, не требующее программирования для использования.

**vs Open Interpreter** — Open Interpreter выполняет код локально, но не
имеет скиллов, мульти-агентов, веб-UI и системы памяти. OWL — полноценная
платформа.

## Подходит для слабого железа

OWL Agent спроектирован для минимального потребления ресурсов:

- **RAM**: ~100-150MB для сервера (без LLM-бэкенда)
- **Диск**: ~50MB исходный код + ~200MB зависимости
- **CPU**: работает на любом x64 процессоре
- **Python**: 3.12+ (рекомендуется 3.14)
- **Нет GPU** — LLM-бэкенд работает отдельно

Тестировалось на:
- Intel Celeron N4020 (2GB RAM) — работает стабильно
- Raspberry Pi 4 (4GB) — работает
- Виртуальные машины с 1 vCPU, 1GB RAM — работает

## Запуск

### Stdlib-сервер (рекомендуется)

```bash
python server_stdlib.py --port 7860
```

### Flask-сервер

```bash
python server.py --port 7860
```

### С указанием LLM-бэкенда

По умолчанию используется `http://localhost:1234/v1` (LM Studio):

```bash
python server_stdlib.py --port 7860 --lm-url http://localhost:1234/v1
```

Или любой другой OpenAI-совместимый endpoint:

```bash
python server_stdlib.py --port 7860 --lm-url http://192.168.0.100:8080/v1
```

### Windows (offline installer)

Запустить `install.bat`, затем `start.bat`.

## Установка зависимостей

```bash
pip install -r requirements.txt
# Или оффлайн (из папки libs):
pip install --no-index --find-links=libs flask openai pydantic
```

## Структура проекта

```
OWLAgent/
├── server.py            # Flask-сервер с REST API
├── server_stdlib.py     # Stdlib-сервер (без Flask)
├── config.py            # Конфигурация
├── middleware.py         # Rate limiting, auth
├── requirements.txt     # Python-зависимости
├── LICENSE              # Apache 2.0
├── index.html           # Веб-UI (single-file)
├── agent/               # Ядро агента
│   ├── core.py          # Tool calling, маршрутизация
│   ├── agent_team.py    # Мульти-агентная система
│   ├── flow_engine.py   # Движок процессов
│   └── memory.py        # Память (SQLite + FTS5)
├── routes/              # API endpoints
│   ├── chat.py          # Чат-эндпоинты
│   ├── flow.py          # Flow Engine API
│   ├── memory.py        # Поиск по памяти
│   ├── provider.py      # Управление LLM-провайдером
│   ├── skills.py        # Управление скиллами
│   ├── system.py        # Системная информация
│   └── teams.py         # Управление командами агентов
├── skills/              # 16 скиллов с CLI-скриптами
├── libs/                # Python-пакеты для оффлайн-установки
├── libs_win/            # Пакеты для Windows (Python 3.12)
├── libs_win314/         # Пакеты для Windows (Python 3.14)
├── memory/              # SQLite база данных агента
├── projects/            # Проекты пользователя
└── static/              # Статические файлы веб-UI
```

## Лицензия

Apache 2.0 — см. файл [LICENSE](LICENSE)
