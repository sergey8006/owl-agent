# Document Reader Skill

Извлечение текста и данных из документов: PDF, DOC, DOCX, TXT, RTF, XLS, XLSX.

## Использование

```
/doc-read /path/to/file.pdf
/doc-read /path/to/report.docx
/doc-read /path/to/data.xlsx
```

Или попросите агента: "прочитай файл document.pdf" или "извлеки данные из таблицы.xlsx"

## Что умеет

- **PDF** — извлечение текста (через pdftotext или встроенный fallback)
- **DOCX** — чтение параграфов, таблиц
- **DOC** — бинарное чтение с извлечением текста
- **TXT/RTF** — прямое чтение
- **XLS/XLSX** — чтение ячеек, листов

## Скрипты

- `read_doc.py <filepath>` — универсальный ридер, автоопределение формата
- `read_doc.py <filepath> --json` — вывод в JSON (для таблиц)
