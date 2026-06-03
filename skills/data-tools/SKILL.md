# Data Tools

Конвертация, валидация, анализ данных: JSON, CSV, YAML, TOML.

## Использование

```bash
# Конвертация между форматами
python data_tool.py convert data.json data.csv
python data_tool.py convert data.csv data.json
python data_tool.py convert config.yaml config.toml

# Валидация
python data_tool.py validate data.json

# Статистика CSV
python data_tool.py stats data.csv --column price

# Слияние JSON
python data_tool.py merge a.json b.json merged.json

# Сравнение JSON
python data_tool.py diff old.json new.json

# Генерация тестовых данных
python data_tool.py generate test.csv --count 100 --columns "id:int,name:str,price:float,date:date"

# Графики из CSV
python data_tool.py chart data.csv chart.png --column price --type line --title "Prices"
python data_tool.py chart data.csv hist.png --column age --type hist --bins 20
```

## Зависимости
- pyyaml, toml, matplotlib (pip install pyyaml toml matplotlib)
