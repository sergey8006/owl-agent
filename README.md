# OWL Agent v3.0 — Offline AI Agent Platform

Локальный AI-агент с мульти-агентной системой, ReAct, RAG, Flow Engine,
планировщиком, вебхуками и полной автономностью. Работает полностью оффлайн
(кроме LLM-бэкенда).

## Возможности

### Агентная система
- **Tool calling** — агент может читать/писать файлы, запускать скрипты,
  искать по памяти, выполнять Python-код
- **ReAct Engine** — цикл Reasoning + Acting: думает → действует → наблюдает → повторяет
  до завершения задачи (как AutoGPT/LangChain)
- **RAG (Retrieval Augmented Generation)** — загрузка документов → чанкинг →
  TF-IDF поиск → генерация ответа с источниками (как LangChain RAG)
- **Task Management** — автогенерация подзадач из цели, приоритизация,
  очередь выполнения (как BabyAGI)
- **Memory System** — SQLite с FTS5-поиском, тегами, дедупликацией.
  Агент помнит контекст между сессиями
- **Agent Teams** — мульти-агентное сотрудничество: несколько агентов
  работают над задачами параллельно
- **Hierarchical Teams** — менеджер-агент декомпозирует задачу, делегирует
  воркерам, ревьюит результаты, итерирует (как CrewAI)
- **16 скиллов** — image-processor, data-analyzer, doc-reader,
  system-monitor, nodejs, project_manager и другие
- **AutoSkill** — агент автоматически создаёт новые скиллы
  из успешных решений

### Flow Engine
- Визуальный редактор процессов (если/иначе, циклы, параллельные ветки)
- Retry с настраиваемым количеством попыток и задержкой
- Checkpointing — сохранение прогресса, восстановление после сбоя
- Execution Log — полная история запусков с таймстампами
- Создание workflow без кода через веб-UI

### Планировщик и интеграции
- **Cron/Interval Scheduler** — запуск flow или команд по расписанию
- **Webhooks** — приём внешних событий для запуска агента (с HMAC-подписью)
- **Secrets Manager** — безопасное хранение API-ключей (AES-шифрование)

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
- **RAG — загрузка и поиск по документам**
- **Task Queue — управление очередью задач**
- **Scheduler — управление расписанием**
- **Webhooks — управление вебхуками**
- **Secrets — управление секретами**

## Сравнение с другими AI-агентами

| Возможность | OWL Agent | AutoGPT | CrewAI | LangGraph | BabyAGI | Open Interpreter |
|---|---|---|---|---|---|---|
| Работа оффлайн | Да | Нет | Нет | Нет | Нет | Частично |
| Веб-UI из коробки | Да | Нет | Нет | Нет | Нет | Нет |
| ReAct pattern | Да | Да | Нет | Нет | Нет | Нет |
| RAG | Да | Нет | Нет | Через расширения | Нет | Нет |
| Task Management | Да | Нет | Нет | Нет | Да | Нет |
| Мульти-агенты | Да | Нет | Да | Да | Нет | Нет |
| Hierarchical Teams | Да | Нет | Да | Нет | Нет | Нет |
| Flow Engine | Да | Нет | Нет | Да | Нет | Нет |
| Scheduler | Да | Нет | Нет | Нет | Нет | Нет |
| Webhooks | Да | Нет | Нет | Нет | Нет | Нет |
| Secrets Manager | Да | Нет | Нет | Нет | Нет | Нет |
| Checkpointing | Да | Нет | Нет | Да | Нет | Нет |
| Скиллы | 16 | Плагины | Tools | Tools | Нет | Нет |
| Память (FTS5) | Да | Ограничено | Нет | State | Векторная | Нет |
| Python only | Да | Да | Да | Да | Да | Да |
| ~100MB RAM | Да | Нет (~1GB+) | Нет | Нет | Нет | Нет |

### Ключевые отличия

**vs AutoGPT** — OWL работает полностью оффлайн, имеет встроенный веб-UI,
RAG, планировщик и вебхуки. AutoGPT требует интернет и OpenAI API.

**vs CrewAI** — CrewAI — фреймворк для разработчиков. OWL — готовое приложение
с графическим интерфейсом, Flow Editor, RAG и оффлайн-установкой.

**vs LangGraph** — LangGraph — библиотека для построения графов агентов.
OWL — автономное приложение с визуальным редактором, не требующее программирования.

**vs BabyAGI** — BabyAGI — только task management. OWL включает всё плюс
ReAct, RAG, Flow Engine, мульти-агентов, веб-UI.

**vs Open Interpreter** — Open Interpreter выполняет код локально, но не
имеет скиллов, мульти-агентов, RAG, планировщика и системы памяти.

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

### Flask-сервер

```bash
python server.py --port 7860
```

### С указанием LLM-бэкенда

```bash
python server.py --port 7860 --lm-url http://localhost:1234/v1
```

### Windows (offline installer)

Запустить `install.bat`, затем `start.bat`.

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## API Endpoints

### Чат
- `POST /api/chat` — отправка сообщения агенту
- `GET /api/chat/history` — история диалога

### ReAct
- `POST /api/react/run` — запуск ReAct цикла для задачи

### RAG
- `POST /api/rag/search` — поиск по базе знаний
- `POST /api/rag/ask` — вопрос с генерацией ответа (RAG)
- `POST /api/rag/index-file` — индексировать файл
- `POST /api/rag/index-dir` — индексировать директорию
- `GET /api/rag/documents` — список документов
- `DELETE /api/rag/document/<id>` — удалить документ

### Task Management
- `GET /api/tasks/list` — список задач
- `POST /api/tasks/create` — создать задачу
- `POST /api/tasks/<id>/complete` — завершить задачу
- `POST /api/tasks/<id>/fail` — отметить как ошибку
- `POST /api/tasks/generate` — автогенерация подзадач из цели

### Scheduler
- `GET /api/scheduler/list` — список задач планировщика
- `POST /api/scheduler/add` — добавить задачу (interval/cron/oneshot)
- `POST /api/scheduler/remove` — удалить задачу
- `POST /api/scheduler/toggle` — включить/выключить
- `POST /api/scheduler/run` — запустить немедленно

### Webhooks
- `POST /api/webhook/register` — зарегистрировать вебхук
- `GET /api/webhook/list` — список вебхуков
- `POST /api/webhook/incoming/<id>` — входящий вебхук
- `POST /api/webhook/delete` — удалить вебхук

### Secrets
- `GET /api/secrets/list` — список ключей
- `POST /api/secrets/set` — сохранить секрет
- `GET /api/secrets/get` — получить секрет
- `POST /api/secrets/delete` — удалить секрет

### Flow Engine
- `GET /api/flow/list` — список flow
- `POST /api/flow/create` — создать flow
- `POST /api/flow/run` — запустить flow
- `POST /api/flow/run` with `{"resume": true}` — возобновить с checkpoint
- `GET /api/flow/execution-log` — история выполнений
- `POST /api/flow/checkpoint/save` — сохранить checkpoint
- `POST /api/flow/checkpoint/clear` — очистить checkpoint

### Agent Teams
- `GET /api/teams` — список команд
- `POST /api/teams/create` — создать команду
- `POST /api/teams/<id>/run` — запустить (последовательно)
- `POST /api/teams/<id>/run-hierarchical` — запустить (иерархически)
- `GET /api/teams/templates` — шаблоны команд

## Структура проекта

```
OWLAgent/
├── server.py              # Flask-сервер с REST API
├── server_stdlib.py       # Stdlib-сервер (без Flask)
├── config.py              # Конфигурация
├── middleware.py           # Rate limiting, auth
├── requirements.txt       # Python-зависимости
├── LICENSE                # Apache 2.0
├── ANALYSIS.md            # Анализ AI-агентов и план внедрения
├── index.html             # Веб-UI (single-file)
├── agent/                 # Ядро агента
│   ├── core.py            # Tool calling, маршрутизация
│   ├── agent_team.py      # Мульти-агентная система + Hierarchical
│   ├── flow_engine.py     # Движок процессов + Checkpointing
│   ├── memory.py          # Память (SQLite + FTS5)
│   ├── react_engine.py    # ReAct loop + Task Management
│   ├── rag_engine.py      # RAG (загрузка, чанкинг, поиск)
│   ├── scheduler.py       # Cron/Interval планировщик
│   └── secrets.py         # Secrets Manager (AES)
├── routes/                # API endpoints
│   ├── chat.py            # Чат-эндпоинты
│   ├── flow.py            # Flow Engine API
│   ├── memory.py          # Поиск по памяти
│   ├── provider.py        # Управление LLM-провайдером
│   ├── skills.py          # Управление скиллами
│   ├── system.py          # Системная информация
│   ├── teams.py           # Управление командами агентов
│   ├── react.py           # ReAct, RAG, Task Management
│   ├── scheduler.py       # Scheduler API
│   ├── webhook.py         # Webhooks API
│   └── secrets.py         # Secrets API
├── skills/                # 16 скиллов с CLI-скриптами
├── libs/                  # Python-пакеты для оффлайн-установки
├── libs_win/              # Пакеты для Windows (Python 3.12)
├── libs_win314/           # Пакеты для Windows (Python 3.14)
├── memory/                # SQLite база данных агента
├── projects/              # Проекты пользователя
└── static/                # Статические файлы веб-UI
```

## Лицензия

Apache 2.0 — см. файл [LICENSE](LICENSE)
