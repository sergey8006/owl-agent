# Git Tools

Работа с git-репозиториями: status, log, diff, commit, branch, init, analyze.

## Использование

```bash
# Статус
python git_tool.py status

# История
python git_tool.py log --count 20
python git_tool.py log --author "John"

# Изменения
python git_tool.py diff
python git_tool.py diff --staged

# Коммит
python git_tool.py commit -m "Fix bug"

# Ветки
python git_tool.py branch
python git_tool.py branch --create feature-x
python git_tool.py branch --delete old-branch

# Инициализация
python git_tool.py init --readme

# Анализ
python git_tool.py analyze

# .gitignore
python git_tool.py ignore --lang python
python git_tool.py ignore --lang node
```
