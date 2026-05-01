@echo off
cd /d "%~dp0"
echo Installing requirements...
py -m pip install --upgrade pip
py -m pip install --upgrade -r requirements-portable.txt
echo.
echo Starting Premium Pet Clinic from source...
py app.py
pause
