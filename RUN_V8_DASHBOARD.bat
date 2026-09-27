@echo off
cd /d "%~dp0"
echo ==========================================
echo EASTERN GAELS V8 - SECOND SCHOOLS UPLOADER FIXED
echo ==========================================
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8010"
python eastern_gaels_v7.py
pause
