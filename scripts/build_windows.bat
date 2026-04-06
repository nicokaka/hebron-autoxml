@echo off
echo.
echo ========================================================
echo   HEBRON AUTO XML - Compilador Windows (PyInstaller)
echo ========================================================
echo.

echo [1/3] Verificando se pasta dist/hebron-autoxml ja existe para limpeza...
if exist dist\HebronAutoXML (
    rmdir /s /q dist\HebronAutoXML
    echo Pasta limpa.
)

echo.
echo [2/3] Instalando dependencias de ambiente (Runtime e Dev)...
pip install -r requirements.txt
pip install -r requirements-dev.txt

echo.
echo [3/3] Iniciando o compilador PyInstaller...
pyinstaller --name "HebronAutoXML" --onedir --windowed --noconfirm --icon="scripts\icon.ico" main.py --clean

echo.
echo ========================================================
echo   BUILD CONCLUIDO!
echo   Sua pasta de distribuicao isolada foi gerada em:
echo   .\dist\HebronAutoXML
echo ========================================================
echo.
pause
