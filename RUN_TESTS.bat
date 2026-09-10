@echo off
title Running 37 Automated Tests
echo ====================================================
echo Running Automated Test Suite
echo ====================================================
call .venv\Scripts\pytest.exe tests/ -v
pause
