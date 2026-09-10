@echo off
title VoltStore E-Commerce Storefront
echo ====================================================
echo Starting VoltStore Storefront on http://127.0.0.1:8000
echo ====================================================
start http://127.0.0.1:8000
call .venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000 --reload
pause
