import os
import shutil
import time
import sys
import tempfile
from unittest.mock import MagicMock
import openpyxl

# --- Setup Fake Ambiente (Massa) ---
SMOKE_DIR = tempfile.mkdtemp(prefix="hebron_smoke_realista_")

excel_path = os.path.join(SMOKE_DIR, "lote_contabil.xlsx")
xml_dir = os.path.join(SMOKE_DIR, "xmls_sefaz")
out_dir = os.path.join(SMOKE_DIR, "output_hebron")

os.makedirs(xml_dir, exist_ok=True)
os.makedirs(out_dir, exist_ok=True)

# --- 1. GERANDO MASSA EXCEL REALISTA ---
CHAVE_NOME = "35230911111111111111550010000001231000000123"
CHAVE_CONTEUDO = "35230922222222222222550010000004561000000456"
CHAVE_FALTANTE = "35230933333333333333550010000007891000000789"
CHAVE_INVALIDA_TEXTO = "NF_COMPRA_X"
CHAVE_INVALIDA_CURTA = "35230911111111111111550010000001231000000" # 41 digitos

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["TIPO", "CHAVE_DE_ACESSO", "FORNECEDOR"])
ws.append(["NFe", CHAVE_NOME, "Empresa Alpha"]) # Válida e Match Nome
ws.append(["CTe", CHAVE_CONTEUDO, "Transportadora Beta"]) # Válida e Match Conteudo
ws.append(["NFe", CHAVE_FALTANTE, "Fornecedor Fantasma"]) # Válida mas Não Existe no HD
ws.append(["NFe", CHAVE_NOME, "Empresa Alpha (Repetida)"]) # Duplicata (Repetindo a 1a)
ws.append(["NFe", CHAVE_INVALIDA_TEXTO, "Erro Digitação"]) # Invalida Logica
ws.append(["NFe", CHAVE_INVALIDA_CURTA, "Erro Tamanho"]) # Invalida Tamanho
wb.save(excel_path)

# --- 2. GERANDO MASSA XMLs REALISTA ---
# Arquivo 1: Match pelo Nome do Arquivo (Fallback não precisa ocorrer)
with open(os.path.join(xml_dir, f"{CHAVE_NOME}-nfe.xml"), 'w') as f:
    f.write("<ns:nfeProc><lixo>Simula conteudo ignorado porque o nome ja resolve = muito rapido</lixo></ns:nfeProc>")

# Arquivo 2: Match pelo Conteúdo (Nome do arquivo bizarro, forçando a leitura de fallback)
with open(os.path.join(xml_dir, "fatura_compra_mes_05_transp_beta_assinado_final.xml"), 'w') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<cteProc xmlns="http://www.portalfiscal.inf.br/cte" versao="3.00">\n')
    f.write('  <CTe xmlns="http://www.portalfiscal.inf.br/cte">\n')
    f.write(f'    <infCte versao="3.00" Id="CTe{CHAVE_CONTEUDO}">\n')
    f.write('       <ide><cUF>35</cUF></ide>\n')
    f.write('    </infCte>\n')
    f.write('  </CTe>\n')
    f.write('</cteProc>\n')

# Arquivo 3: Ruído visual (Um arquivinho que não ajuda em nada pra testar resiliência)
with open(os.path.join(xml_dir, "arquivo_de_erro.txt"), 'w') as f:
    f.write("Apenas para provar que arquivos não-XML são ignorados.")


# --- 3. MOCKING TKINTER E APP INJECTION ---
class MockCTkClass:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def resizable(self, *args): pass
    def configure(self, *args, **kwargs): pass
    def after(self, ms, callback, *args): callback(*args)
mock_ctk = MagicMock()
mock_ctk.CTk = MockCTkClass
mock_tk = MagicMock()
sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['customtkinter'] = mock_ctk

from src.gui.app import HebronApp

print("[SMOKE REALISTA] Iniciando App...")
app = HebronApp()
app._agendar_ui_update = lambda callback: callback()
app.off_excel_path = MagicMock(); app.off_excel_path.get.return_value = excel_path
app.off_xml_base = MagicMock(); app.off_xml_base.get.return_value = xml_dir
app.off_out_path = MagicMock(); app.off_out_path.get.return_value = out_dir
app.modo_ativo = MagicMock(); app.modo_ativo.get.return_value = "Busca Local"

app.lbl_status = MagicMock()
app.lbl_lidas = MagicMock()
app.lbl_validas = MagicMock()
app.lbl_baixadas = MagicMock()
app.progress_bar = MagicMock()
app.seg_button = MagicMock()
app.f_stats = MagicMock()
app.btn_processar = MagicMock()
app.btn_abrir_pasta = MagicMock()

# --- 4. EXECUTANDO FLUXO DA GUI ---
print("[SMOKE REALISTA] Disparando Processamento via GUI...")
app.iniciar_roteamento()
time.sleep(1.5)

# --- 5. VALIDAÇÕES CRÍTICAS DO DOMÍNIO ---
print("[SMOKE REALISTA] Processamento Terminado. Validando Física e Analítica...")
pasta_gerada = app.ultima_pasta_gerada

assert os.path.exists(pasta_gerada), "Falha Crítica: Pasta de output não instanciada."
folder_xmls = os.path.join(pasta_gerada, "xmls")
xmls_copiados = [f for f in os.listdir(folder_xmls) if f.endswith(".xml")]

# Deve existir exatos 2 arquivos copiados (Match Nome + Match Conteudo)
assert len(xmls_copiados) == 2, f"Erro: Esperávamos isolar 2 XMLs genuinos, isolamos {len(xmls_copiados)}"
print(f"[OK] XMLs Copeados Corretamente: {xmls_copiados}")

planilhas = [f for f in os.listdir(pasta_gerada) if f.endswith(".xlsx")]
assert len(planilhas) == 1, "Planilha XLS nao criada!"

zips = [f for f in os.listdir(pasta_gerada) if f.endswith(".zip")]
assert len(zips) == 1, "ZIP logico master nao empacotado."

# Checando Asserções de Texto da GUI (Garante Analytics Perfeito pro Usuário)
args_lbl, kwargs_lbl = app.lbl_lidas.configure.call_args
texto_ui_lidas = str(kwargs_lbl['text'])
assert texto_ui_lidas == "6", f"Contagem de Leituras falhou: esperado 6, deu {texto_ui_lidas}"

args_lbl, kwargs_lbl = app.lbl_validas.configure.call_args
texto_ui_validas = str(kwargs_lbl['text'])
assert texto_ui_validas == "3", f"Contagem de Validas falhou: esperado 3, deu {texto_ui_validas}"

args_lbl, kwargs_lbl = app.lbl_baixadas.configure.call_args
texto_ui_baixadas = str(kwargs_lbl['text'])
assert texto_ui_baixadas == "2", f"Contagem de Baixadas falhou: esperado 2, deu {texto_ui_baixadas}"

print("[OK] Toda a cadeia lógica de UI exibiu Feedback Realista perfeitamente calibrado!")

try:
    shutil.rmtree(SMOKE_DIR)
except OSError:
    pass
print("\n🔥 [Veredito Final] SMOKE TEST ESTÚPIDO DE REALISTA PASSED! PODE INICIAR O BUNDLE! 🔥")
