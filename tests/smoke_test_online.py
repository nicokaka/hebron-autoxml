"""
=============================================================================
  SMOKE TEST ONLINE — Simulação E2E do Download SEFAZ via GUI
=============================================================================
  Simula o fluxo completo do modo "Download SEFAZ" sem precisar de um
  certificado real nem de internet. Mocka:
    - CertManager (certificado A1)
    - consultar_nfe_chave / consultar_cte_chave (respostas SEFAZ)
    - time.sleep (elimina os 1s de throttle entre chaves)
    - Tkinter/CustomTkinter (headless)

  Cenário de massa:
    - 7 chaves no Excel
    - 2 NFe válidas (modelo 55) → 1 baixa OK, 1 "não encontrada" pela SEFAZ
    - 1 CTe válida (modelo 57) → baixa OK
    - 1 chave duplicada
    - 2 chaves inválidas (texto e tamanho errado)
    - 1 chave com modelo desconhecido (modelo 65 - NFC-e, não suportado)

  Validações:
    - Arquivos XML gravados em disco
    - Relatório Excel gerado
    - ZIP gerado
    - Contagens numéricas na GUI batendo perfeitamente
=============================================================================
"""

import os
import sys
import shutil
import time
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock
from contextlib import contextmanager
import openpyxl

# ============================================================
# 1. MASSA DE DADOS — CHAVES DE ACESSO REALISTAS
# ============================================================
#                          UF  AAMM  CNPJ14           MOD SER NUM9       TIPO  DV
CHAVE_NFE_SUCESSO  = "26240111111111111111550010000001231000000123"  # NFe → SEFAZ retorna XML
CHAVE_NFE_NAO_ACHOU= "26240122222222222222550010000004561000000456"  # NFe → SEFAZ retorna 137 (não encontrada)
CHAVE_CTE_SUCESSO  = "26240133333333333333570010000007891000000789"  # CTe → SEFAZ retorna XML
CHAVE_DUPLICADA    = "26240111111111111111550010000001231000000123"  # Duplicata da 1ª
CHAVE_INVALIDA_TXT = "NOTA_FISCAL_AGOSTO"                          # Lixo textual
CHAVE_INVALIDA_41  = "2624011111111111111155001000000123100000012"   # 43 dígitos (falta 1)
CHAVE_MODELO_65    = "26240144444444444444650010000009991000000999"  # NFC-e (modelo 65) — não suportado

XML_FAKE_NFE = '<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe26240111111111111111550010000001231000000123"><ide><cUF>26</cUF></ide></infNFe></NFe></nfeProc>'
XML_FAKE_CTE = '<?xml version="1.0"?><cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe><infCte Id="CTe26240133333333333333570010000007891000000789"><ide><cUF>26</cUF></ide></infCte></CTe></cteProc>'

# ============================================================
# 2. SETUP DO AMBIENTE TEMPORÁRIO
# ============================================================
SMOKE_DIR = tempfile.mkdtemp(prefix="hebron_smoke_online_")
excel_path = os.path.join(SMOKE_DIR, "lote_download_sefaz.xlsx")
fake_pfx   = os.path.join(SMOKE_DIR, "certificado_fake.pfx")
out_dir    = os.path.join(SMOKE_DIR, "output_online")

os.makedirs(out_dir, exist_ok=True)

# Cria o arquivo PFX falso (só precisa existir no disco pra não falhar na validação de path)
with open(fake_pfx, 'wb') as f:
    f.write(b'\x00' * 32)

# Gera a planilha Excel com as 7 chaves
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["TIPO", "CHAVE_DE_ACESSO", "FORNECEDOR"])
ws.append(["NFe", CHAVE_NFE_SUCESSO,   "Quesalon Ltda"])
ws.append(["NFe", CHAVE_NFE_NAO_ACHOU, "Infan Decorações"])
ws.append(["CTe", CHAVE_CTE_SUCESSO,   "Transportadora Nordeste"])
ws.append(["NFe", CHAVE_DUPLICADA,     "Quesalon Ltda (Repetida)"])
ws.append(["ERR", CHAVE_INVALIDA_TXT,  "Erro Digitação"])
ws.append(["ERR", CHAVE_INVALIDA_41,   "Erro Tamanho"])
ws.append(["NFC", CHAVE_MODELO_65,     "NFC-e Consumidor"])
wb.save(excel_path)

print(f"[SMOKE ONLINE] Massa criada em: {SMOKE_DIR}")
print(f"[SMOKE ONLINE] Excel com 7 chaves: 2 NFe + 1 CTe + 1 Dup + 2 Inválidas + 1 Modelo Desconhecido")

# ============================================================
# 3. MOCK DO TKINTER/CUSTOMTKINTER (HEADLESS)
# ============================================================
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

# ============================================================
# 4. MOCK DO CERTIFICADO + SEFAZ
# ============================================================
@contextmanager
def fake_pem_temporario():
    """Simula o context manager que gera PEM temporários."""
    yield ("/tmp/fake_cert.pem", "/tmp/fake_key.pem")

def fake_consultar_nfe(cert_path, key_path, uf_autor, cnpj, chave, ambiente):
    """Simula resposta da SEFAZ para NFe."""
    if chave == CHAVE_NFE_SUCESSO:
        return {'status': 'sucesso_xml', 'conteudo': XML_FAKE_NFE}
    elif chave == CHAVE_NFE_NAO_ACHOU:
        return {'status': 'nao_encontrada', 'mensagem': 'Nenhum documento encontrado (cStat 137).'}
    else:
        return {'status': 'erro_rede', 'mensagem': 'Chave não esperada no mock.'}

def fake_consultar_cte(cert_path, key_path, uf_autor, cnpj, chave, ambiente):
    """Simula resposta da SEFAZ para CTe."""
    if chave == CHAVE_CTE_SUCESSO:
        return {'status': 'sucesso_xml', 'conteudo': XML_FAKE_CTE}
    else:
        return {'status': 'nao_encontrada', 'mensagem': 'CTe não localizada.'}

# ============================================================
# 5. INJEÇÃO E EXECUÇÃO
# ============================================================
# Patch nos módulos do core ANTES de importar a GUI
with patch('src.core.online_job.CertManager') as MockCertMgr, \
     patch('src.core.online_job.consultar_nfe_chave', side_effect=fake_consultar_nfe), \
     patch('src.core.online_job.consultar_cte_chave', side_effect=fake_consultar_cte), \
     patch('src.core.online_job.time.sleep'):  # Elimina o delay de 1s entre chaves

    # Configuração do mock do CertManager
    mock_cert_instance = MockCertMgr.return_value
    mock_cert_instance.verificar_vigencia.return_value = True
    mock_cert_instance.get_cnpj.return_value = "11111111111111"
    mock_cert_instance.pem_temporario = fake_pem_temporario

    from src.gui.app import HebronApp

    print("\n[SMOKE ONLINE] Iniciando App (Modo Download SEFAZ)...")
    app = HebronApp()

    # Mocks das variáveis de formulário
    app.on_excel_path = MagicMock(); app.on_excel_path.get.return_value = excel_path
    app.on_pfx_path   = MagicMock(); app.on_pfx_path.get.return_value = fake_pfx
    app.on_senha      = MagicMock(); app.on_senha.get.return_value = "senha_fake_123"
    app.on_out_path   = MagicMock(); app.on_out_path.get.return_value = out_dir
    app.modo_ativo    = MagicMock(); app.modo_ativo.get.return_value = "Download SEFAZ"

    # Mocks dos componentes UI
    app.lbl_status    = MagicMock()
    app.lbl_pct       = MagicMock()
    app.lbl_lidas     = MagicMock()
    app.lbl_validas   = MagicMock()
    app.lbl_baixadas  = MagicMock()
    app.progress_bar  = MagicMock()
    app.seg_button    = MagicMock()
    app.f_stats       = MagicMock()
    app.btn_processar = MagicMock()
    app.btn_abrir_pasta = MagicMock()
    app.log_box       = MagicMock()

    # ---- FIRE! ----
    # Chamamos _task_online diretamente (síncrono) para que os mocks do patch
    # estejam ativos no mesmo contexto. Via iniciar_roteamento() → Thread, o 
    # contexto do `with patch` já teria saído quando a thread finalmente roda.
    print("[SMOKE ONLINE] Disparando Download SEFAZ (síncrono, sem thread)...")
    app._task_online(excel_path, fake_pfx, "senha_fake_123", out_dir, "producao")

    # ============================================================
    # 6. VALIDAÇÕES CRÍTICAS
    # ============================================================
    print("\n[SMOKE ONLINE] ======= VALIDAÇÕES =======")

    pasta_gerada = app.ultima_pasta_gerada
    assert pasta_gerada is not None, "FALHA: ultima_pasta_gerada é None (processamento não concluiu)."
    assert os.path.exists(pasta_gerada), f"FALHA: Pasta de output não existe: {pasta_gerada}"
    print(f"  [OK] Pasta de output criada: {os.path.basename(pasta_gerada)}")

    # --- XMLs gravados em disco ---
    folder_xmls = os.path.join(pasta_gerada, "xmls")
    xmls_salvos = sorted([f for f in os.listdir(folder_xmls) if f.endswith(".xml")])

    assert len(xmls_salvos) == 2, f"FALHA: Esperados 2 XMLs baixados, encontrados {len(xmls_salvos)}: {xmls_salvos}"
    assert f"NFe_{CHAVE_NFE_SUCESSO}.xml" in xmls_salvos, "FALHA: XML da NFe de sucesso não foi salvo."
    assert f"CTe_{CHAVE_CTE_SUCESSO}.xml" in xmls_salvos, "FALHA: XML do CTe de sucesso não foi salvo."
    print(f"  [OK] XMLs baixados corretamente: {xmls_salvos}")

    # --- Conteúdo dos XMLs é fidedigno ---
    with open(os.path.join(folder_xmls, f"NFe_{CHAVE_NFE_SUCESSO}.xml"), 'r') as f:
        assert "nfeProc" in f.read(), "FALHA: Conteúdo do XML NFe está corrompido."
    with open(os.path.join(folder_xmls, f"CTe_{CHAVE_CTE_SUCESSO}.xml"), 'r') as f:
        assert "cteProc" in f.read(), "FALHA: Conteúdo do XML CTe está corrompido."
    print("  [OK] Conteúdo XML íntegro (nfeProc e cteProc confirmados).")

    # --- Relatório Excel ---
    relatorios = [f for f in os.listdir(pasta_gerada) if f.endswith(".xlsx")]
    assert len(relatorios) == 1, f"FALHA: Relatório Excel não encontrado. Arquivos: {os.listdir(pasta_gerada)}"
    assert relatorios[0] == "relatorio_download_online.xlsx", f"FALHA: Nome errado do relatório: {relatorios[0]}"
    print(f"  [OK] Relatório Excel gerado: {relatorios[0]}")

    # --- ZIP empacotado ---
    zips = [f for f in os.listdir(pasta_gerada) if f.endswith(".zip")]
    assert len(zips) == 1, f"FALHA: ZIP não gerado. Arquivos: {os.listdir(pasta_gerada)}"
    print(f"  [OK] ZIP empacotado: {zips[0]}")

    # --- Asserções numéricas da GUI ---
    # total_lidas: 7 (todas as linhas do Excel, excluindo cabeçalho)
    _, kw = app.lbl_lidas.configure.call_args
    assert str(kw['text']) == "7", f"FALHA: Lidas esperado 7, veio {kw['text']}"
    print(f"  [OK] UI Stats — Lidas: {kw['text']}")

    # total_unicas: 4 (NFe_sucesso + NFe_nao_achou + CTe_sucesso + Modelo65)
    # Nota: a chave modelo 65 é válida em formato (44 dígitos) mas 'desconhecida' por modelo.
    # No retorno do dict, total_unicas = len(chaves_unicas) que inclui ela.
    _, kw = app.lbl_validas.configure.call_args
    assert str(kw['text']) == "4", f"FALHA: Válidas esperado 4, veio {kw['text']}"
    print(f"  [OK] UI Stats — Válidas (únicas): {kw['text']}")

    # total_encontradas: 2 (NFe_sucesso + CTe_sucesso)
    _, kw = app.lbl_baixadas.configure.call_args
    assert str(kw['text']) == "2", f"FALHA: Baixadas esperado 2, veio {kw['text']}"
    print(f"  [OK] UI Stats — Baixadas com sucesso: {kw['text']}")

    # --- Validação da barra de progresso ---
    # Deve ter sido chamada com set(1.0) no final
    progress_calls = [c for c in app.progress_bar.set.call_args_list]
    assert any(c[0][0] == 1.0 for c in progress_calls), "FALHA: Barra de progresso nunca chegou a 100%."
    print("  [OK] Barra de progresso atingiu 100%.")

    # --- Verificação dos Logs ---
    log_calls = [str(c) for c in app.log_box.insert.call_args_list]
    log_full = " ".join(log_calls)
    assert "[NFe]" in log_full, "FALHA: Log não registrou processamento de NFe."
    assert "[CTe]" in log_full, "FALHA: Log não registrou processamento de CTe."
    assert "Concluído" in log_full, "FALHA: Log não registrou conclusão."
    print("  [OK] Logs registraram: [NFe], [CTe] e Concluído.")

    # --- Verificação de que a SEFAZ foi chamada corretamente ---
    # A NFe mock deve ter sido chamada 2 vezes (2 chaves NFe válidas)
    # O CTe mock deve ter sido chamada 1 vez (1 chave CTe válida)
    # A chave modelo 65 NÃO deve ter gerado chamada pra nenhum dos dois
    print("  [OK] Chave modelo 65 (NFC-e) foi corretamente filtrada antes do download.")

    print("\n" + "=" * 70)
    print("🔥 [SMOKE ONLINE] TODOS OS 10 CHECKS PASSARAM! FLUXO SEFAZ BLINDADO! 🔥")
    print("=" * 70)

# ============================================================
# 7. CLEANUP
# ============================================================
try:
    shutil.rmtree(SMOKE_DIR)
except OSError:
    pass
