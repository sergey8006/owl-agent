# Project Manager Skill (AutoSkill)

Автоматическое создание и запуск проектов по шаблонам.

## Использование

```
/launch_project <name> [type]
```

Типы проектов:
- `python` — Python проект (main.py, requirements.txt, README.md)
- `web` — Web проект (index.html, style.css, app.js)
- `data` — Data Science проект (notebook.ipynb, data/, output/)

## Что делает

1. Создаёт папку проекта `/mnt/c/2/projects/<name>/`
2. Генерирует файлы по шаблону
3. Создаёт README.md с описанием
4. Запускает setup скрипт если есть

## API

- `POST /api/launch_project` — создать проект
- `GET /api/projects` — список проектов
- `DELETE /api/projects/<name>` — удалить проект

## Шаблоны

Шаблоны хранятся в `/mnt/c/2/templates/`:
- `templates/python/` — Python шаблон
- `templates/web/` — Web шаблон
- `templates/data/` — Data Science шаблон
