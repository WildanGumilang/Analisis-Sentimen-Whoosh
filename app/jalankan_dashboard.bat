@echo off
REM Menjalankan dashboard Streamlit. Buka http://localhost:8501 di browser.
REM Hentikan dengan Ctrl+C atau tutup jendela ini.
cd /d "%~dp0.."
set TMP=D:\wg\.cache\tmp2
set TEMP=D:\wg\.cache\tmp2
".venv\Scripts\streamlit.exe" run app\streamlit_app.py --server.port 8501
