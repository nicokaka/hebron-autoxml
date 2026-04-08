import pytest
from unittest.mock import patch, MagicMock
from src.core.online_job import iniciar_download_sefaz
from src.core.cert_manager import CertificadoInvalidoError
from tests.conftest import CHAVE_ENTRADA, CHAVE_SAIDA, CHAVE_CTE

@pytest.fixture
def base_mocks(mock_temp_dir):
    with patch("src.core.online_job.CertManager") as MockCertManager, \
         patch("src.core.online_job.ler_coluna_b") as mock_ler, \
         patch("src.core.online_job.classificar_chaves") as mock_classificar, \
         patch("src.core.online_job.remover_duplicadas") as mock_dedup, \
         patch("src.core.online_job.enviar_manifestacao") as mock_manifestar, \
         patch("src.core.online_job.baixar_lote_nsu") as mock_distnsu, \
         patch("src.core.online_job.consultar_nfe_chave") as mock_consch, \
         patch("src.core.online_job.SefazPortalScraper") as MockScraper, \
         patch("src.core.online_job.time.sleep") as mock_sleep, \
         patch("src.core.online_job.get_cached_nsu", return_value="100"), \
         patch("src.core.online_job.save_nsu"), \
         patch("src.core.online_job.gerar_relatorio_excel"), \
         patch("src.core.online_job.gerar_zip_arquivos"), \
         patch("src.core.online_job.get_downloaded", return_value={}), \
         patch("src.core.online_job.mark_downloaded"), \
         patch("src.core.online_job.get_cooldown_remaining", return_value=0), \
         patch("src.core.online_job.clear_blocked"), \
         patch("src.core.online_job.try_recover_xml", return_value=None), \
         patch("src.core.online_job.mark_blocked"):
        
        mock_cert = MagicMock()
        mock_cert.get_cnpj.return_value = "08939548000103"
        mock_cert.get_uf.return_value = ("26", "PE")
        mock_cert.pem_temporario.return_value.__enter__.return_value = ("cert.pem", "key.pem")
        MockCertManager.return_value = mock_cert

        # Por padrão o Playwright scraper retorna dict vazio (nenhuma chave processada)
        # Os testes individuais podem sobrescrever com mock_scraper.return_value.baixar_xmls.return_value
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.baixar_xmls.return_value = {}
        MockScraper.return_value = mock_scraper_instance
        
        yield {
            "cert": mock_cert,
            "ler": mock_ler,
            "classificar": mock_classificar,
            "dedup": mock_dedup,
            "manifestar": mock_manifestar,
            "distnsu": mock_distnsu,
            "consch": mock_consch,
            "scraper_cls": MockScraper,
            "scraper": mock_scraper_instance,
            "sleep": mock_sleep,
            "dir": mock_temp_dir
        }

def test_flow_happy_path(base_mocks):
    """
    Testa o fluxo com 1 Entrada.
    Manifesta -> Delay -> distNSU -> 100% resolvidas
    """
    m = base_mocks
    m["ler"].return_value = [CHAVE_ENTRADA]
    m["classificar"].return_value = ([CHAVE_ENTRADA], []) # validas, invalidas
    m["dedup"].return_value = ([CHAVE_ENTRADA], []) # unicas, duplicadas
    
    # Manifestacao ok
    m["manifestar"].return_value = {CHAVE_ENTRADA: "135"}
    
    # Lote acha o XML procNFe
    fake_xml_b64 = "H4sIAAAAAAAA/yvPL8pJAQCErI3iBAAAAA==" # compactado basico pra nao crashar (b64 do zip de 'abc')
    import base64; import gzip
    real_zip = base64.b64encode(gzip.compress(f'<procNFe><chNFe>{CHAVE_ENTRADA}</chNFe></procNFe>'.encode())).decode()
    m["distnsu"].return_value = {
        'status': 'sucesso', 'ultNSU': '101', 'maxNSU': '101',
        'docs': [{'schema': 'procNFe', 'content_b64': real_zip}]
    }

    logs = []
    res = iniciar_download_sefaz("input.xlsx", "fake.pfx", "senha", m["dir"], on_progresso=lambda m, *args: logs.append(m))
    
    # Como foi achado no distNSU (Fase 3), nao deve ir pra Fase 4 (Fallback)
    m["consch"].assert_not_called()
    assert res['total_encontradas'] == 1
    assert any("[Passo 1] Manifestação" in l for l in logs)
    assert any("[Passo 3] distNSU" in l for l in logs)

def test_flow_fallback_and_656(base_mocks):
    """
    Testa o limite 656.
    Playwright retorna vazio (nenhuma chave) -> cai pro WebService legado.
    O 1º consChNFe toma 656 -> hard stop.
    """
    m = base_mocks
    # Chaves de SAIDA: pula manifestação/distNSU, vai direto pro Passo 4
    m["ler"].return_value = [CHAVE_SAIDA, CHAVE_SAIDA.replace("4", "5")]
    m["classificar"].return_value = ([CHAVE_SAIDA, CHAVE_SAIDA.replace("4", "5")], [])
    m["dedup"].return_value = ([CHAVE_SAIDA, CHAVE_SAIDA.replace("4", "5")], [])
    
    # distNSU retorna vazio
    m["distnsu"].return_value = {'status': 'vazio', 'ultNSU': '100', 'maxNSU': '100'}

    # Playwright não baixa nenhuma (retorna dict vazio -> chaves_para_legado = todas)
    m["scraper"].baixar_xmls.return_value = {}
    
    # 1ª tentativa WebService dá 656
    m["consch"].return_value = {'status': 'rejeitado_656', 'mensagem': 'Rate-limit'}
    
    logs = []
    with patch("src.core.online_job.mark_blocked") as mock_mark_blocked:
        res = iniciar_download_sefaz("input.xlsx", "fake.pfx", "senha", m["dir"], on_progresso=lambda m, *args: logs.append(m))
        mock_mark_blocked.assert_called_once()
        
    # consChNFe deve ter sido chamado exatamente UMA vez (tomo 656 -> abort)
    m["consch"].assert_called_once()
    assert res['total_encontradas'] == 0
    assert any("HARD STOP" in l for l in logs)

def test_flow_alerta_cancelado(base_mocks):
    """
    Se o popup retornar False, o fluxo tem early abort.
    """
    m = base_mocks
    m["ler"].return_value = [CHAVE_SAIDA]
    m["classificar"].return_value = ([CHAVE_SAIDA], [])
    m["dedup"].return_value = ([CHAVE_SAIDA], [])
    
    logs = []
    # Retorna False no callback
    res = iniciar_download_sefaz(
        "ex.xlsx", "fake.pfx", "senha", m["dir"],
        on_progresso=lambda m, *args: logs.append(m),
        on_alerta_saidas=lambda eta_dict: False
    )
    
    # Nenhum processamento ocorreu
    m["manifestar"].assert_not_called()
    m["distnsu"].assert_not_called()
    assert any("Operação cancelada" in l for l in logs)
