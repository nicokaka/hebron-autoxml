import os
import shutil
import time
import sys
from unittest.mock import MagicMock
import openpyxl

# --- Setup Fake Ambiente (Massa) ---
SMOKE_DIR = "/home/nicolas/.gemini/antigravity/scratch/smoke_test"
os.makedirs(SMOKE_DIR, exist_ok=True)

excel_path = os.path.join(SMOKE_DIR, "contabilidade_extrato.xlsx")
xml_dir = os.path.join(SMOKE_DIR, "fake_sefaz")
out_dir = os.path.join(SMOKE_DIR, "resultado_hebron")

os.makedirs(xml_dir, exist_ok=True)
os.makedirs(out_dir, exist_ok=True)

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["ID", "CHAVE", "R$"])
ws.append(["1", "35230000000000000000000000000000000000000111", "Encontrada"])
ws.append(["2", "35230000000000000000000000000000000000000222", "Faltante"])
ws.append(["3", "35230000000000000000000000000000000000000111", "Duplicada"])
ws.append(["4", "LIXO123", "Invalida"])
wb.save(excel_path)

with open(os.path.join(xml_dir, "nota_fiscal_35230000000000000000000000000000000000000111-nfe.xml"), 'w') as f:
    f.write("<fake_xml_body></fake_xml_body>")

# --- MOCKING TKINTER ---
class MockCTkClass:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def resizable(self, *args): pass
    
mock_ctk = MagicMock()
mock_ctk.CTk = MockCTkClass
mock_tk = MagicMock()

sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['customtkinter'] = mock_ctk

from src.gui.app import HebronApp

# --- HUMANO SIMULADO ---
print("[SMOKE] Iniciando GUI Mínima...")
app = HebronApp()

# Emulando a sincronicidade dos testes (Substituindo o '.after' puro pro Python cru rodar as msgs)
app._agendar_ui_update = lambda callback: callback()

# 2. Preencher os 3 Caminhos 
app.excel_path = MagicMock()
app.excel_path.get.return_value = excel_path
app.xml_base_path = MagicMock()
app.xml_base_path.get.return_value = xml_dir
app.output_path = MagicMock()
app.output_path.get.return_value = out_dir

app.lbl_status = MagicMock()
app.btn_processar = MagicMock()
app.btn_abrir_pasta = MagicMock()

print("[SMOKE] Clicando em 'Processar'...")
app.iniciar_processamento()

# Aguardar a Thead do Core fazer seu Mágico I/O
time.sleep(1) 

print("[SMOKE] Verificando Artefatos Gerados...")
pasta_gerada = app.ultima_pasta_gerada
print(f"Pasta gerada registrada: {pasta_gerada}")

assert os.path.exists(pasta_gerada), "ERRO: Pasta de Processados não existe."

folder_xmls = os.path.join(pasta_gerada, "xmls")
assert os.path.exists(folder_xmls), "ERRO: Subpasta 'xmls' não existe."

xmls_copiados = [f for f in os.listdir(folder_xmls) if f.endswith(".xml")]
assert len(xmls_copiados) == 1, f"ERRO: Esperava 1 XML copiado. Achou: {len(xmls_copiados)}"

planilhas = [f for f in os.listdir(pasta_gerada) if f.endswith(".xlsx")]
assert len(planilhas) == 1, "ERRO: Relatóro XLSX não foi emitido."

zips = [f for f in os.listdir(pasta_gerada) if f.endswith(".zip")]
assert len(zips) == 1, "ERRO: Arquivo ZIP não foi emitido."

print("[SMOKE] Tudo OK. Limpando Massa...")
shutil.rmtree(SMOKE_DIR)
print("[SMOKE] Finalizado com SUCESSO!")
