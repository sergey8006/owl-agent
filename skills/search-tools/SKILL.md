# Search Tools

Поиск по файлам: grep, regex, replace, duplicates, big files.

## Использование

```bash
# Полнотекстовый поиск
python search_tool.py grep "hello" ./src/
python search_tool.py grep "TODO" . --max 50

# Regex-поиск
python search_tool.py regex "\d{4}-\d{2}-\d{2}" ./logs/ -i

# Поиск и замена
python search_tool.py replace "old" "new" "./src/**/*.py" --dry-run

# Дубликаты
python search_tool.py duplicates ./Downloads/

# Большие файлы
python search_tool.py bigfiles /home --min-size 1024 --limit 20
```
