@echo off
python generate_dbg.py || exit /b 1
python -m pytest . || exit /b 1
