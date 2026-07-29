@echo off
cd /d "%~dp0.."
python -m pip install requests urllib3 -q
python fetch_andon_raw.py
