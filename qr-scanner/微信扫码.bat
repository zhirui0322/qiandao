@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
title Classroom QR Scanner

rem 找一个能用的 python：优先 py 启动器，其次 PATH 里的 python
set "PY=python"
where py >nul 2>nul && set "PY=py -3"

echo ============================================================
echo   Classroom QR Scanner
echo   capture classroom screen -^> decode QR -^> print result
echo   hit screenshots are saved in qr_hits\
echo ============================================================
echo.

if not "%~1"=="" goto run
echo Scanning today's classroom, ppt and camera.
echo Press Ctrl+C to stop.
echo.
%PY% scan_qr.py --channels ppt,main --interval 2 --timeout 1800 --copy
goto done

:run
%PY% scan_qr.py %*

:done
echo.
pause
