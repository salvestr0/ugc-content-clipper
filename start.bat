@echo off
title Viral Clipper
cd /d "%~dp0"

:: Add Python Scripts and static-ffmpeg to PATH so yt-dlp / ffmpeg are found
for /f "delims=" %%i in ('python -c "import sys, pathlib; print(pathlib.Path(sys.executable).parent / 'Scripts')"') do set "SCRIPTS=%%i"
for /f "delims=" %%i in ('python -c "import static_ffmpeg; p=static_ffmpeg.run.get_or_fetch_platform_executables_else_raise(); import os; print(os.path.dirname(p[0]))"') do set "FFDIR=%%i"
set "PATH=%SCRIPTS%;%FFDIR%;%PATH%"

start http://localhost:8000
python run_web.py
pause
