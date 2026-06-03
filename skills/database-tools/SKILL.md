# Database Tools

Работа с SQLite: запросы, схема, экспорт, импорт, бэкап, оптимизация.

## Использование

```bash
# Выполнить SQL-запрос
python db_tool.py query data.db "SELECT * FROM users LIMIT 10"
python db_tool.py query data.db "DELETE FROM logs WHERE date < '2024-01-01'"

# Список таблиц
python db_tool.py tables data.db

# Схема таблицы
python db_tool.py schema data.db --table users

# Экспорт
python db_tool.py export data.db users output.csv
python db_tool.py export data.db users output.json

# Импорт из CSV
python db_tool.py import data.db new_table input.csv

# Бэкап
python db_tool.py backup data.db --output data.backup.db

# Оптимизация
python db_tool.py optimize data.db

# Статистика
python db_tool.py stats data.db
```

## Зависимости
- Только Python stdlib (sqlite3)
