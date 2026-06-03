# Archive Tools

Работа с архивами: ZIP, TAR, GZ, BZ2, XZ.

## Использование

```bash
# Создать архив
python archive_tool.py create file1.txt file2.txt output.zip
python archive_tool.py create dir1/ dir2/ output.tar.gz --format gz
python archive_tool.py create *.py output.tar.bz2 --format bz2

# Распаковать
python archive_tool.py extract archive.zip
python archive_tool.py extract archive.tar.gz --output ./extracted/

# Список содержимого
python archive_tool.py list archive.zip

# Сравнение архивов
python archive_tool.py compare old.zip new.zip
```

## Зависимости
- Только Python stdlib (zipfile, tarfile)
