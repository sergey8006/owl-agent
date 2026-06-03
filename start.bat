@echo off 
chcp 65001 >nul 2>&1 
cd /d "%~dp0" 
if exist ".venv\Scripts\python.exe" ( 
  .venv\Scripts\python.exe server.py --port 7860 
) else ( 
  python server.py --port 7860 
) 
