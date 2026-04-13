"""
Testes unitários para portal_scraper.py.
Usa mocks do Playwright — sem necessidade de navegador real.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ─── Helpers de mock ────────────────────────────────────────────────────────

def _make_scraper_mocked():
    """
    Retorna um SefazPortalScraper com um _page mock já injetado.
    Evita importar playwright nos testes.
    """
    from src.core.portal_scraper import SefazPortalScraper
    from src.core.captcha_solver import CaptchaSolverError

    logs = []
    scraper = SefazPortalScraper(on_progresso=lambda m: logs.append(m))

    # Injetar page mock diretamente (bypass _iniciar_browser)
    page_mock = MagicMock()
    scraper._page    = page_mock
    scraper._browser = MagicMock()
    scraper._pw      = MagicMock()

    return scraper, page_mock, logs


CHAVE_TESTE = "26260400446820000101550250000004251000014685"


# ─── Testes de _verificar_playwright ────────────────────────────────────────

def test_verificar_playwright_disponivel():
    """Não deve lançar exceção quando playwright está instalado."""
    from src.core.portal_scraper import SefazPortalScraper
    # O playwright está instalado no venv, então não deve lançar
    SefazPortalScraper._verificar_playwright()


def test_verificar_playwright_indisponivel():
    """Deve lançar PlaywrightIndisponivel quando import falha."""
    from src.core.portal_scraper import SefazPortalScraper, PlaywrightIndisponivel
    with patch("builtins.__import__", side_effect=ImportError("playwright")):
        with pytest.raises((PlaywrightIndisponivel, ImportError)):
            SefazPortalScraper._verificar_playwright()


# ─── Testes de _tentar_consulta ─────────────────────────────────────────────

def test_tentar_consulta_sucesso_resumo(tmp_path):
    """Quando painel tem conteúdo real mas sem link XML → sucesso_resumo."""
    scraper, page_mock, logs = _make_scraper_mocked()

    # Simular que wait_for_function retorna (não lança exceção)
    page_mock.wait_for_function.return_value = None

    # Simular painel com texto de nota real
    resumo_locator = MagicMock()
    resumo_locator.inner_text.return_value = (
        "Situação Atual: Autorizada\n"
        "Natureza da Operação: Venda\n"
        "Emitente: Fornecedor LTDA"
    )
    resumo_locator.inner_html.return_value = "<div>Situação Atual: Autorizada...</div>"
    page_mock.locator.return_value = resumo_locator

    # Sem link de XML
    page_mock.query_selector.return_value = None

    status = scraper._tentar_consulta(CHAVE_TESTE, str(tmp_path), tentativa=1)

    assert status == "sucesso_resumo"
    assert (tmp_path / f"Resumo_{CHAVE_TESTE}.html").exists()


def test_tentar_consulta_captcha_timeout(tmp_path):
    """Quando wait_for_function lança TimeoutError → captcha_timeout."""
    scraper, page_mock, logs = _make_scraper_mocked()

    page_mock.wait_for_function.side_effect = Exception("Timeout 180000ms exceeded")

    status = scraper._tentar_consulta(CHAVE_TESTE, str(tmp_path), tentativa=1)

    assert status == "captcha_timeout"


def test_tentar_consulta_captcha_invalido(tmp_path):
    """Quando painel contém texto de captcha inválido → captcha_invalido."""
    scraper, page_mock, logs = _make_scraper_mocked()

    page_mock.wait_for_function.return_value = None

    resumo_locator = MagicMock()
    resumo_locator.inner_text.return_value = "O Captcha é inválido. Falha na validação. Tente novamente."
    resumo_locator.inner_html.return_value = "<div>Captcha invalido</div>"
    page_mock.locator.return_value = resumo_locator

    status = scraper._tentar_consulta(CHAVE_TESTE, str(tmp_path), tentativa=1)

    assert status == "captcha_invalido"


def test_tentar_consulta_chave_nao_encontrada(tmp_path):
    """Quando painel indica nota não encontrada → chave_nao_encontrada."""
    scraper, page_mock, logs = _make_scraper_mocked()

    page_mock.wait_for_function.return_value = None

    resumo_locator = MagicMock()
    resumo_locator.inner_text.return_value = "Chave de Acesso não encontrada na base de dados."
    resumo_locator.inner_html.return_value = "<div>Chave nao encontrada</div>"
    page_mock.locator.return_value = resumo_locator

    status = scraper._tentar_consulta(CHAVE_TESTE, str(tmp_path), tentativa=1)

    assert status == "chave_nao_encontrada"


def test_tentar_consulta_sucesso_xml(tmp_path):
    """Quando há link de download → _baixar_xml_direto é chamado → sucesso_xml."""
    scraper, page_mock, logs = _make_scraper_mocked()

    page_mock.wait_for_function.return_value = None

    resumo_locator = MagicMock()
    resumo_locator.inner_text.return_value = "Situação Atual: Autorizada\nEmitente: LTDA"
    resumo_locator.inner_html.return_value = "<div>ok</div>"
    page_mock.locator.return_value = resumo_locator

    # Link de download presente
    link_mock = MagicMock()
    page_mock.query_selector.return_value = link_mock

    # Simular download bem-sucedido
    dl_ctx = MagicMock()
    dl_ctx.__enter__ = MagicMock(return_value=dl_ctx)
    dl_ctx.__exit__ = MagicMock(return_value=False)
    dl_mock = MagicMock()
    dl_ctx.value = dl_mock
    page_mock.expect_download.return_value = dl_ctx

    status = scraper._tentar_consulta(CHAVE_TESTE, str(tmp_path), tentativa=1)

    assert status == "sucesso_xml"
    dl_mock.save_as.assert_called_once()

def test_tentar_consulta_auto_captcha(tmp_path):
    """Quando tem api_key, deve chamar solver.resolver_hcaptcha e injetar token."""
    from src.core.portal_scraper import SefazPortalScraper
    
    logs = []
    scraper = SefazPortalScraper(on_progresso=lambda m: logs.append(m), captcha_api_key="12345")
    
    page_mock = MagicMock()
    scraper._page = page_mock
    scraper._browser = MagicMock()
    scraper._pw = MagicMock()
    
    # Mock do CaptchaSolver interno
    solver_mock = MagicMock()
    solver_mock.resolver_hcaptcha.return_value = "TOKEN_FALSO"
    scraper._solver = solver_mock
    
    # Simular wait_for_selector retornando um elemento com data-sitekey
    el_mock = MagicMock()
    el_mock.get_attribute.return_value = "SITEKEY_123"
    page_mock.wait_for_selector.return_value = el_mock
    
    # Simular sucesso_resumo pós injeção
    page_mock.wait_for_function.return_value = None
    resumo_locator = MagicMock()
    resumo_locator.inner_text.return_value = "Situação Atual: Autorizada"
    resumo_locator.inner_html.return_value = "<div>ok</div>"
    page_mock.locator.return_value = resumo_locator
    page_mock.query_selector.return_value = None
    
    status = scraper._tentar_consulta(CHAVE_TESTE, str(tmp_path), tentativa=1)
    
    solver_mock.resolver_hcaptcha.assert_called_once_with("SITEKEY_123", page_mock.url)
    page_mock.evaluate.assert_called_once()
    assert "TOKEN_FALSO" == page_mock.evaluate.call_args[0][1]
    assert status == "sucesso_resumo"
    
def test_tentar_consulta_auto_captcha_erro_api(tmp_path):
    """Quando a API de captcha falha, deve retornar erro_captcha_api."""
    from src.core.portal_scraper import SefazPortalScraper
    from src.core.captcha_solver import CaptchaSolverError
    
    logs = []
    scraper = SefazPortalScraper(on_progresso=lambda m: logs.append(m), captcha_api_key="12345")
    page_mock = MagicMock()
    scraper._page = page_mock
    
    solver_mock = MagicMock()
    solver_mock.resolver_hcaptcha.side_effect = CaptchaSolverError("Zero balance")
    scraper._solver = solver_mock
    
    el_mock = MagicMock()
    el_mock.get_attribute.return_value = "SITEKEY_123"
    page_mock.wait_for_selector.return_value = el_mock
    
    status = scraper._tentar_consulta(CHAVE_TESTE, str(tmp_path), tentativa=1)
    
    assert status == "erro_captcha_api"


# ─── Teste de retry de captcha inválido ─────────────────────────────────────

def test_processar_chave_retry_captcha_invalido(tmp_path):
    """
    Quando captcha_invalido ocorre, deve tentar até _MAX_RETRIES_CAPTCHA vezes
    e retornar 'captcha_invalido' se todas falharem.
    """
    from src.core.portal_scraper import SefazPortalScraper, _MAX_RETRIES_CAPTCHA

    scraper, page_mock, logs = _make_scraper_mocked()

    page_mock.wait_for_function.return_value = None

    resumo_locator = MagicMock()
    resumo_locator.inner_text.return_value = "O Captcha é inválido. Falha na validação."
    resumo_locator.inner_html.return_value = "<div>falha captcha</div>"
    page_mock.locator.return_value = resumo_locator

    status = scraper._processar_chave(CHAVE_TESTE, str(tmp_path))

    assert status == "captcha_invalido"
    # Deve ter tentado _MAX_RETRIES_CAPTCHA vezes
    assert page_mock.goto.call_count == _MAX_RETRIES_CAPTCHA


# ─── Teste de baixar_xmls (integração interna) ───────────────────────────────

def test_baixar_xmls_sucesso_parcial(tmp_path):
    """Teste end-to-end interno com 2 chaves, uma com sucesso e outra com timeout."""
    from src.core.portal_scraper import SefazPortalScraper

    chave_ok     = "26260400446820000101550250000004251000014685"
    chave_falha  = "26260400446820000101550250000004251000014686"

    logs = []
    scraper = SefazPortalScraper(on_progresso=lambda m: logs.append(m))

    # Mock completo do _iniciar_browser e _fechar_browser
    scraper._pw      = MagicMock()
    scraper._browser = MagicMock()
    page_mock = MagicMock()
    scraper._page = page_mock

    call_count = [0]

    def fake_wait_for_function(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return None  # chave_ok: captcha ok
        raise Exception("Timeout")  # chave_falha: timeout

    page_mock.wait_for_function.side_effect = fake_wait_for_function

    resumo_locator = MagicMock()
    resumo_locator.inner_text.return_value = "Situação Atual: Autorizada\nEmitente: OK"
    resumo_locator.inner_html.return_value = "<div>ok</div>"
    page_mock.locator.return_value = resumo_locator
    page_mock.query_selector.return_value = None

    with patch.object(scraper, "_iniciar_browser", return_value=None), \
         patch.object(scraper, "_fechar_browser", return_value=None):
        resultados = scraper.baixar_xmls([chave_ok, chave_falha], str(tmp_path))

    assert resultados[chave_ok]    == "sucesso_resumo"
    assert resultados[chave_falha] == "captcha_timeout"
    assert any("1/2" in l for l in logs)
