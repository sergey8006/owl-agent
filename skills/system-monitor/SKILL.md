# System Monitor

Мониторинг системы: CPU, RAM, диски, сеть, процессы, порты.

## Использование

```bash
# Общая информация
python system_tool.py info

# CPU
python system_tool.py cpu

# Память
python system_tool.py memory

# Диски
python system_tool.py disk
python system_tool.py disk --path /home

# Сеть
python system_tool.py network

# Процессы
python system_tool.py processes --limit 20
python system_tool.py processes --search python

# Открытые порты
python system_tool.py ports

# Установленные пакеты
python system_tool.py packages --search flask --limit 20
```

## Зависимости
- Только Python stdlib (psutil опционально)
