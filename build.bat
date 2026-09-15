@echo off
REM builds dist\SimpleRemap.exe
pip install -r requirements.txt pyinstaller
pyinstaller --onefile --windowed --icon=icon.ico --add-data "icon.ico;." --name SimpleRemap main.py
