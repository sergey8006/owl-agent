# OWL Agent v2.0 — Offline AI Chat

Локальный AI-агент с поддержкой tool calling, скиллов и веб-UI.

## Запуск

```bash
# Основной сервер (stdlib)
python server_stdlib.py --port 7860

# Flask-сервер
python server.py --port 7860

# С удалённым LM Studio
python server_stdlib.py --port 7860 --lm-url http://26.221.39.194:1234/v1
```

## Установка зависимостей

```bash
pip install -r requirements.txt
# Или оффлайн:
pip install --no-index --find-links=libs flask openai pydantic
```

## Структура

- `server_stdlib.py` — основной сервер с 17 инструментами
- `server.py` — Flask-сервер
- `index.html` — веб-UI
- `skills/` — 14 скиллов с CLI-скриптами
- `libs/` — 58 Python-пакетов + 5 JS-библиотек для оффлайн-работы
- `memory/` — SQLite база данных агента

## Возможности

- 17 инструментов: файловые операции, скрипты, память, скиллы
- 14 скиллов: image-processor, data-tools, text-tools, system-monitor, database-tools, archive-tools, git-tools, search-tools, ai-image-gen, web-scraper, file-organizer, code-reviewer, doc-reader, data-analyzer
- Веб-UI: чат, файловый менеджер, редактор скриптов, панель скиллов
- Полностью оффлайн (кроме LM Studio)
