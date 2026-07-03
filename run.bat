@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\王政\AppData\Local\Programs\Python\Python311\python.exe" -B -m streamlit run app.py
pause
