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

## 2. Gerando o Primeiro Empacotamento / Build (.exe p/ Windows)

A arquitetura do MVP 1 foi preparada estritamente de maneira Modular. Para testar o primeiro build independente de instalador focado na estabilidade da compilação visual:

Gere um repositório isolado em Windows rodando o motor `PyInstaller`:

```powershell
pyinstaller --name "HebronAutoXML" --onedir --windowed --noconfirm main.py
```

Isso instruirá a AST do PyInstaller a não encostar no lixo contido em pacotes obsoletos como `prova_tecnica/` ou `/tests/`. A raiz contida em `dist/HebronAutoXML/` poderá ser compactada inteiramente após gerada e transferida à Usuária-Alvo para rodar simplesmente clicando no `HebronAutoXML.exe`.

*Status: Aprovado p/ Build. Faltam etapas de empacotamento MSI/InnoSetup estático.*
