# Text Tools

Обработка текста: поиск, замена, diff, статистика, кодировки, base64.

## Использование

```bash
# Поиск по файлам (grep)
python text_tool.py grep "pattern" ./src/
python text_tool.py grep "error" /var/log/ -i --max 50

# Поиск и замена
python text_tool.py replace "old_text" "new_text" "*.py"
python text_tool.py replace "\d+" "NUM" "*.txt" --dry-run

# Сравнение файлов
python text_tool.py diff file1.txt file2.txt

# Статистика текста
python text_tool.py stats document.txt --top 20

# Конвертация кодировки
python text_tool.py encoding input.txt --from windows-1251 --to utf-8 --output output.txt

# Base64
python text_tool.py base64 file.bin --output encoded.txt
python text_tool.py base64 encoded.txt --decode --output decoded.bin

# Hex
python text_tool.py hex file.bin
python text_tool.py hex encoded.hex --decode --output file.bin

# Генерация markdown-отчёта
python text_tool.py report --title "Analysis" --input source.txt --data data.json --output report.md
```
