# Data Analyzer

Анализ данных: статистика, визуализация, отчёты.

## Использование

Используйте data-tool.py из скилла data-tools для анализа данных:

```bash
# Статистика CSV
python ../data-tools/scripts/data_tool.py stats data.csv --column price

# Генерация графиков
python ../data-tools/scripts/data_tool.py chart data.csv chart.png --column sales --type bar
```

Для сложного анализа используйте Python напрямую через script_exec.
