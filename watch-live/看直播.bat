@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Classroom Live

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python 3.9+ not found. Install Python first.
  pause
  exit /b 1
)

%PY% watch_live.py %*
if errorlevel 1 pause
