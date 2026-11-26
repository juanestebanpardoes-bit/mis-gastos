@echo off
set PY=C:\Users\juan\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PY%" (
  echo No se encontro Python en "%PY%".
  echo Ajusta la variable PY en este archivo a tu ruta de Python.
  pause
  exit /b 1
)
start "" http://127.0.0.1:8000
"%PY%" "%~dp0app.py"
pause
