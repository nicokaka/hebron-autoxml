@echo off
title Construindo HebronAutoXML
echo ==============================================
echo  HebronAutoXML - Gerador de Executavel (Windows)
echo ==============================================
echo.

echo 1. Instalando Dependencias e Empacotador...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo 2. Empacotando o Aplicativo em Arquivo Unico (.exe)...
pyinstaller --noconfirm --onefile --windowed --name "HebronAutoXML_v2" --add-data "%LOCALAPPDATA%\Programs\Python\Python312\Lib\site-packages\customtkinter;customtkinter/" --hidden-import openpyxl --hidden-import cryptography --hidden-import requests --hidden-import urllib3 main.py

echo.
echo ==============================================
echo  [SUCESSO] Construcao Concluida!
echo  Verifique a pasta "dist" para achar o HebronAutoXML_v2.exe
echo ==============================================
pause
