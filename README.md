# HebronAutoXML - MVP 1 Offline

O MVP 1 foca estritamente na validação paramétrica e cruzamento primário (Matching Híbrido) dos arquivos XML contra a base em Excel emitida pela contabilidade, garantindo a organização massiva dos relatórios sem necessidade transitória de conexão Sefaz via Certificados.

## Pré-requisitos
- Python 3.11+ ou superior
- Ambiente local ativado
- Windows 10/11 (Para versão UI executável)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 1. Executando pela Interface Gráfica (Source)
O projeto agora possui Frontend puro guiado pelo `customtkinter`.

```bash
python main.py
```
- Informe a Planilha `.xlsx`
- Aponte para sua Pasta raiz de Backups Sefaz Locais
- Aponte a sua Pasta de Output
- Pressione Processar. Ao final, a interface emitirá um resumo e um Relatório Formatado + ZIP para entrega limpa.

## 2. Gerando o Empacotamento para Usuário Final (.exe)

O Build (modo `onedir`) converte todo este projeto cru em uma pasta nativa independente de instalação do Python.
**IMPORTANTE:** O binário do Windows só pode ser emitido rolando essas instruções em um SO Windows!

1. Em sua máquina ou VM **Windows**, abra o Terminal/PowerShell na raiz do projeto.
2. Certifique-se de que iniciou seu ambiente virtual (`venv\Scripts\activate`).
3. Rode o novo script automatizado de empacotamento:
   ```cmd
   .\scripts\build_windows.bat
   ```

**Onde o artefato cai?** O script vai instalar o `PyInstaller` (via `requirements-dev.txt`) e soltar sua pasta limpa em `dist/HebronAutoXML/`. Essa pasta inteira será o software. Quando as futuras definições de _Installer Wizard (InnoSetup)_ vierem, elas beberão dessa fonte.
