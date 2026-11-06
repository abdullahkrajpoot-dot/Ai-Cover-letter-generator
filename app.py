"""Streamlit entry point.

Run with: streamlit run app.py --server.address 127.0.0.1 --server.port 8501
The maintained UI remains in streamlit_app.py for backward compatibility with run.bat.
"""
from pathlib import Path

ui_path = Path(__file__).with_name("streamlit_app.py")
exec(compile(ui_path.read_text(encoding="utf-8"), str(ui_path), "exec"))
