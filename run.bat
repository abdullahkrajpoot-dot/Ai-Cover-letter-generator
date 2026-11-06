@echo off
cd /d %~dp0
if exist .venv_new\Scripts\python.exe (
  .venv_new\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
) else (
  if not exist venv python -m venv venv
  venv\Scripts\python.exe -m pip install -r requirements.txt
  venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
)
