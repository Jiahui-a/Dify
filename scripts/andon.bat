@echo off
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo [info] creating venv...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install -e ".[dev]" -q
python -m andon_fetcher %*
