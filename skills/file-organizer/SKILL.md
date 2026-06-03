# File Organizer Skill

Автоматическая сортировка файлов по папкам по типу.

## Использование

```
python organize.py /path/to/directory [--dry-run] [--recursive] [--undo]
```

Или просто попросите агента: "отсортируй файлы в папке C:\Downloads"

## Что делает

- Изображения → `Images/`
- Документы → `Documents/`
- Видео → `Video/`
- Музыка → `Music/`
- Архивы → `Archives/`
- Код → `Code/`
- Данные → `Data/`
- Исполняемые → `Executables/`
- Шрифты → `Fonts/`
- Прочее → `Other/`

## Параметры

- `--dry-run` — показать что будет перемещено, без действий
- `--recursive` — сортировать и в подпапках
- `--undo` — вернуть файлы обратно в корень

## Через API

POST /api/skill_run
{
  "skill_id": "file-organizer",
  "script": "organize.py",
  "args": "C:\\Users\\Downloads --dry-run"
}
