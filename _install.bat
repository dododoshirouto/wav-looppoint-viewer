@echo off

IF EXIST venv\Scripts\activate GOTO :SKIP_CREATE_VENV
    python -m venv venv
:SKIP_CREATE_VENV

"venv\Scripts\python.exe" -m pip install -r requirements.txt