@echo off
setlocal
cd /d "%~dp0\.."
"%~dp0..\..\python\python.exe" -m streamlit run app.py --server.headless=true --server.port=%APP_PORT%
endlocal
