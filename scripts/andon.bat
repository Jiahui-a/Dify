@echo off
REM 在仓库根目录 Dify 下运行本脚本，或先 cd 到 Dify
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo [info] creating venv...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install -e ".[dev]" -q
python -m andon_fetcher %*
