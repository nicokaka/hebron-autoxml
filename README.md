# 🛡️ HebronAutoXML v2.0

**Automated XML processor for Brazilian tax documents (NF-e / CT-e)**

Built to solve a real problem I kept running into at accounting firms: spending hours manually hunting down XML files from SEFAZ or digging through massive folders just to find specific invoices. This tool automates the entire workflow — from reading access keys out of a spreadsheet to downloading documents directly from SEFAZ's national servers using A1 digital certificates.

> 🇧🇷 [Leia em Português](#-português)

---

## What it does

HebronAutoXML has two operating modes:

### ⬇️ SEFAZ Download
Connects directly to the Brazilian Federal Revenue servers (NF-e and CT-e distribution services) using your `.pfx` digital certificate. You point it at an Excel file with access keys in column B, and it downloads every XML it can find, generates a detailed report, and packages everything into a `.zip`.

### 🔍 Local Search
Already have thousands of XML files scattered across folders? This mode reads your spreadsheet and intelligently scans your local directories — matching by filename first, then falling back to parsing the XML content itself. It pulls out exactly the files you need and ignores everything else.

## Key features

- **A1 Certificate support** — Reads `.pfx` files, extracts CNPJ automatically, validates expiration before every request
- **Smart key validation** — Filters out duplicates, malformed keys, and unsupported document types before touching the network
- **Anti-throttle compliance** — 1-second delay between SEFAZ requests to respect rate limits
- **Detailed Excel reports** — Every run generates a spreadsheet logging the status of each key (downloaded, not found, duplicate, invalid, etc.)
- **Dark mode UI** — Clean, modern interface built with CustomTkinter. No command line needed
- **Thread-safe processing** — Heavy I/O runs on background threads so the UI never freezes
- **Production-locked** — Environment is hardcoded to production (mirroring how FSist and similar tools work). No accidental test-mode runs

## Tech stack

- Python 3.12
- CustomTkinter (GUI)
- OpenPyXL (Excel read/write)
- Cryptography (PFX/PEM certificate handling)
- Requests (SOAP/mTLS communication with SEFAZ)
- PyInstaller (Windows executable packaging)
- GitHub Actions (automated CI/CD builds)

## Getting started

### From the release (recommended)
1. Go to [Releases](../../releases) and download `HebronAutoXML_v2.exe`
2. Double-click to run. No installation needed

### From source
```bash
git clone https://github.com/nicokaka/hebron-autoxml.git
cd hebron-autoxml
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

### Running tests
```bash
PYTHONPATH=. python -m unittest discover -s tests -v
PYTHONPATH=. python tests/smoke_test_realista.py
PYTHONPATH=. python tests/smoke_test_online.py
```

## Project structure

```
hebron-autoxml/
├── main.py                          # Entry point
├── src/
│   ├── gui/
│   │   └── app.py                   # UI layout, callbacks, threading
│   ├── core/
│   │   ├── parser_excel.py          # Column B reader with float→int guard
│   │   ├── key_validator.py         # 44-digit validation
│   │   ├── deduplicador.py          # Duplicate removal (preserves order)
│   │   ├── classificador_tipo.py    # Model classification (55=NFe, 57=CTe)
│   │   ├── cert_manager.py          # PFX loading, PEM generation, CNPJ extraction
│   │   ├── sefaz_nfe.py             # NFe distribution service client
│   │   ├── sefaz_cte.py             # CTe distribution service client
│   │   ├── sefaz_tools.py           # SOAP parsing, GZIP decompression
│   │   ├── matcher_xml.py           # Local XML indexer (filename + content fallback)
│   │   ├── online_job.py            # SEFAZ download orchestrator
│   │   └── offline_job.py           # Local search orchestrator
│   └── io_reports/
│       ├── report_writer.py         # Excel report generator
│       └── zipper.py                # ZIP packaging
├── tests/                           # Unit tests + E2E smoke tests
├── .github/workflows/               # CI/CD (Windows build + Release)
└── HebronAutoXML.spec               # PyInstaller config (onefile)
```

## How it works under the hood

1. **Excel parsing** — Reads column B starting from row 2, converting Excel's numeric values back to proper 44-digit strings (prevents scientific notation corruption)
2. **Validation pipeline** — Keys go through format validation → deduplication → model classification (NFe vs CTe vs unsupported)
3. **Certificate handling** — The `.pfx` is loaded once, CNPJ is extracted from the certificate's subject field, and temporary PEM files are generated inside a context manager (auto-cleanup guaranteed)
4. **SEFAZ communication** — SOAP 1.2 requests over mTLS to the national distribution endpoints. Responses are parsed for `cStat` codes, and GZIP-compressed XML documents are extracted from base64-encoded `docZip` tags
5. **Output packaging** — Successfully downloaded/found XMLs are saved to a timestamped folder, a detailed report is generated, and everything gets zipped

## License

MIT

---

# 🇧🇷 Português

# 🛡️ HebronAutoXML v2.0

**Processador automático de XMLs para documentos fiscais brasileiros (NF-e / CT-e)**

Criei essa ferramenta pra resolver um problema que eu via acontecer todo mês nos escritórios de contabilidade: perder horas catando XML na SEFAZ ou vasculhando pastas gigantescas pra achar notas específicas. O HebronAutoXML automatiza o fluxo inteiro — desde a leitura das chaves de acesso numa planilha até o download dos documentos diretamente pelos servidores nacionais da SEFAZ usando certificado digital A1.

## O que faz

O HebronAutoXML tem dois modos de operação:

### ⬇️ Download SEFAZ
Conecta direto nos servidores da Receita Federal (serviços de distribuição de NF-e e CT-e) usando seu certificado digital `.pfx`. Você aponta pra um Excel com as chaves de acesso na coluna B, e ele baixa todos os XMLs que encontrar, gera um relatório detalhado e empacota tudo num `.zip`.

### 🔍 Busca Local
Já tem milhares de XMLs espalhados em pastas? Esse modo lê sua planilha e varre os diretórios locais de forma inteligente — primeiro tenta bater pelo nome do arquivo, depois faz fallback lendo o conteúdo do XML. Separa exatamente os arquivos que você precisa e ignora o resto.

## Funcionalidades principais

- **Certificado A1** — Lê arquivos `.pfx`, extrai o CNPJ automaticamente, valida vencimento antes de cada requisição
- **Validação inteligente de chaves** — Filtra duplicatas, chaves mal formatadas e tipos de documento não suportados antes de bater na rede
- **Conformidade anti-throttle** — 1 segundo de delay entre requisições à SEFAZ pra respeitar os limites
- **Relatórios detalhados em Excel** — Cada execução gera uma planilha com o status de cada chave (baixada, não encontrada, duplicada, inválida, etc.)
- **Interface dark mode** — UI limpa e moderna feita com CustomTkinter. Sem necessidade de linha de comando
- **Processamento thread-safe** — I/O pesado roda em threads separadas pra interface nunca congelar
- **Travado em produção** — Ambiente fixo em produção (igual FSist e ferramentas similares). Sem risco de rodar em modo de testes por acidente

## Como usar

### Pelo Release (recomendado)
1. Vá em [Releases](../../releases) e baixe o `HebronAutoXML_v2.exe`
2. Dê dois cliques pra rodar. Não precisa instalar nada

### Pelo código fonte
```bash
git clone https://github.com/nicokaka/hebron-autoxml.git
cd hebron-autoxml
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt
python main.py
```

### Rodando os testes
```bash
PYTHONPATH=. python -m unittest discover -s tests -v
PYTHONPATH=. python tests/smoke_test_realista.py
PYTHONPATH=. python tests/smoke_test_online.py
```

## Licença

MIT
