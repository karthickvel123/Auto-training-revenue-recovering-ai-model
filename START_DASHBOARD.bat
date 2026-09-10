@echo off
title Merchant AI Recovery Dashboard
echo ====================================================
echo Starting Merchant AI Dashboard on http://localhost:8501
echo ====================================================
start http://localhost:8501
call .venv\Scripts\streamlit.exe run dashboard\app.py --server.port 8501
pause
