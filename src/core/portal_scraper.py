"""
SefazPortalScraper — Download de XMLs via Portal Público da SEFAZ (Playwright)

Estratégia: Modo SEMI-AUTOMÁTICO (headed).
- O robô navega, digita as chaves e extrai os dados da página.
- O USUÁRIO resolve o hCaptcha manualmente quando solicitado (~10 seg).
- Sem rate-limit de WebService: 300 chaves em ~30 min vs 15h no fallback.
- Custo: R$ 0.

Ciclo de vida:
  1. Abre Chromium/Edge headed (janela visível)
  2. Para cada chave: navega → preenche → aguarda captcha → extrai resultado
  3. Se a página tiver link de download do XML, baixa. Se não, salva o HTML
     estruturado como evidência.
  4. Retorna dict {chave: "sucesso_xml" | "sucesso_resumo" | "erro_xxx"}
"""

import os
import time
import logging
from typing import Callable, Dict

log = logging.getLogger(__name__)

# ─── Constantes do Portal SEFAZ ──────────────────────────────────────────────

_PORTAL_URL = (
    "https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx"
    "?tipoConsulta=resumo&tipoConteudo=7PhJ+gAVw2g="
)

# Seletores CSS mapeados via inspeção ao vivo do portal (abril/2025)
_SEL_INPUT_CHAVE   = "#ctl00_ContentPlaceHolder1_txtChaveAcessoResumo"
_SEL_BTN_CONTINUAR = "#ctl00_ContentPlaceHolder1_btnConsultar"
_SEL_RESUMO_PAINEL = "#ctl00_ContentPlaceHolder1_upResumo"
_SEL_LINK_XML      = "a[href*='downloadNFe'], a[href*='downloadXML'], a[id*='btnDownload']"

# Timeouts
_TIMEOUT_CAPTCHA_MS = 180_000   # 3 min para o usuário resolver o captcha
_TIMEOUT_NAV_MS     = 20_000    # 20s para carregar a página inicial

# Textos que indicam captcha inválido (SEFAZ exibe em vermelho na página)
_ERROS_CAPTCHA = [
    "captcha é inválido",
    "falha na validação",
    "o captcha",
    "tente novamente",
]

# Textos que indicam nota não encontrada
_ERROS_NOTA_NAO_ENCONTRADA = [
    "chave de acesso não encontrada",
    "não existe nf-e",
    "nenhum resultado",
    "nota fiscal não encontrada",
    "documento não encontrado",
]

# Sentinela de conteúdo que prova que a consulta foi bem-sucedida
_CONTEUDO_POSITIVO = [
    "situação atual",
    "natureza da operação",
    "data de emissão",
    "emitente",
    "cnpj",
]

_MAX_RETRIES_CAPTCHA = 3  # Quantas vezes tenta o captcha por chave


# ─── Exceção Customizada ──────────────────────────────────────────────────────

class PlaywrightIndisponivel(Exception):
    """Playwright não instalado ou navegador não encontrado."""


# ─── Scraper Principal ────────────────────────────────────────────────────────

class SefazPortalScraper:
    """
    Orquestra o download de XMLs via portal público da SEFAZ usando Playwright.

    Usage:
        scraper = SefazPortalScraper(on_progresso=log_fn)
        resultados = scraper.baixar_xmls(chaves, pasta_saida)
        # resultados: {"chave44digs": "sucesso_xml" | "erro_xxx", ...}
    """

    def __init__(self, on_progresso: Callable = None):
        self._on_prog = on_progresso or (lambda msg: None)
        self._browser = None
        self._page    = None
        self._pw      = None

    # ── API Pública ──────────────────────────────────────────────────────────

    def baixar_xmls(
        self,
        chaves: list,
        pasta_saida: str,
    ) -> Dict[str, str]:
        """
        Itera sobre a lista de chaves, abrindo o portal para cada uma.

        Retorna:
            dict {chave: status}
            status in {"sucesso_xml", "sucesso_resumo", "captcha_timeout",
                       "captcha_invalido", "chave_nao_encontrada",
                       "erro_pagina", "erro_geral"}
        """
        self._verificar_playwright()
        os.makedirs(pasta_saida, exist_ok=True)

        resultados: Dict[str, str] = {}
        total = len(chaves)

        self._on_prog(
            f"[Portal SEFAZ] Abrindo navegador para {total} chave(s)..."
        )
        self._on_prog(
            "[Portal SEFAZ] ATENCAO: Uma janela do navegador vai abrir. "
            "Resolva o captcha quando solicitado e NAO feche a janela."
        )

        try:
            self._iniciar_browser()

            for idx, chave in enumerate(chaves):
                self._on_prog(
                    f"[Portal SEFAZ] [{idx + 1}/{total}] Consultando: {chave[:20]}..."
                )
                status = self._processar_chave(chave, pasta_saida)
                resultados[chave] = status
                self._on_prog(
                    f"[Portal SEFAZ]   -> {status}"
                )

        except Exception as e:
            self._on_prog(f"[Portal SEFAZ] ERRO FATAL: {e}")
            log.exception("Erro fatal no SefazPortalScraper")
        finally:
            self._fechar_browser()

        ok = sum(1 for s in resultados.values() if s.startswith("sucesso"))
        self._on_prog(
            f"[Portal SEFAZ] Concluido: {ok}/{total} baixadas com sucesso."
        )
        return resultados

    # ── Navegação Interna ────────────────────────────────────────────────────

    def _processar_chave(self, chave: str, pasta_saida: str) -> str:
        """
        Fluxo completo para uma chave com retry em captcha inválido.

        Retorna o status string.
        """
        for tentativa in range(1, _MAX_RETRIES_CAPTCHA + 1):
            try:
                status = self._tentar_consulta(chave, pasta_saida, tentativa)
                if status != "captcha_invalido":
                    return status
                # Captcha inválido → recarregar e tentar de novo
                self._on_prog(
                    f"[Portal SEFAZ]   [!] Captcha invalido (tentativa {tentativa}/{_MAX_RETRIES_CAPTCHA}). "
                    "Recarregando pagina para nova tentativa..."
                )
                time.sleep(1)

            except Exception as e:
                log.warning("Erro na tentativa %d para %s: %s", tentativa, chave, e)
                self._capturar_screenshot(chave, f"erro_tentativa_{tentativa}")
                if tentativa == _MAX_RETRIES_CAPTCHA:
                    return "erro_pagina"

        return "captcha_invalido"

    def _tentar_consulta(self, chave: str, pasta_saida: str, tentativa: int) -> str:
        """
        Uma tentativa de consulta para a chave. Retorna status string.
        """
        # ── 1. Navegar ao portal ──
        self._page.goto(_PORTAL_URL, wait_until="domcontentloaded",
                        timeout=_TIMEOUT_NAV_MS)

        # ── 2. Preencher chave ──
        input_el = self._page.wait_for_selector(
            _SEL_INPUT_CHAVE, timeout=10_000
        )
        input_el.fill(chave)

        # ── 3. Instruir o usuário ──
        msg_tentativa = f" (tentativa {tentativa})" if tentativa > 1 else ""
        self._on_prog(
            f"[Portal SEFAZ]   [CAPTCHA{msg_tentativa}] Resolva na janela do navegador "
            "e clique em 'Continuar'. Aguardando ate 3 minutos..."
        )

        # ── 4. Aguardar resultado pós-captcha ──────────────────────────────
        # ESTRATÉGIA CORRETA: aguardar uma navegação/reload na mesma URL
        # que indique que o form foi submetido com sucesso.
        # O painel #upResumo JÁ EXISTE antes do captcha (vazio).
        # Precisamos detectar que ele GANHOU CONTEÚDO REAL.
        # Usamos wait_for_function para poll o innerHTML até ter texto relevante
        # ou uma mensagem de erro conhecida.

        try:
            self._page.wait_for_function(
                """() => {
                    const el = document.querySelector('#ctl00_ContentPlaceHolder1_upResumo');
                    if (!el) return false;
                    const t = el.innerText || '';
                    // Conteúdo real da nota
                    if (t.toLowerCase().includes('situação atual') ||
                        t.toLowerCase().includes('situacao atual') ||
                        t.toLowerCase().includes('natureza da operação') ||
                        t.toLowerCase().includes('emitente') ||
                        t.toLowerCase().includes('data de emissão') ||
                        t.toLowerCase().includes('valor total')) return true;
                    // Nota não encontrada
                    if (t.toLowerCase().includes('chave de acesso não encontrada') ||
                        t.toLowerCase().includes('não existe nf-e') ||
                        t.toLowerCase().includes('nenhum resultado')) return true;
                    // Captcha inválido (vermelho)
                    if (t.toLowerCase().includes('captcha') ||
                        t.toLowerCase().includes('falha na validação') ||
                        t.toLowerCase().includes('tente novamente')) return true;
                    return false;
                }""",
                timeout=_TIMEOUT_CAPTCHA_MS,
            )
        except Exception:
            self._capturar_screenshot(chave, "captcha_timeout")
            return "captcha_timeout"

        # Pequena espera para o JS do UpdatePanel terminar de renderizar
        time.sleep(1.0)

        # ── 5. Ler conteúdo do painel ──
        try:
            painel_texto = self._page.locator(_SEL_RESUMO_PAINEL).inner_text()
            painel_html  = self._page.locator(_SEL_RESUMO_PAINEL).inner_html()
        except Exception:
            return "erro_pagina"

        painel_lower = painel_texto.lower()

        # ── 6. Detectar captcha inválido ──
        if any(err in painel_lower for err in _ERROS_CAPTCHA):
            return "captcha_invalido"

        # ── 7. Detectar nota não encontrada ──
        if any(err in painel_lower for err in _ERROS_NOTA_NAO_ENCONTRADA):
            return "chave_nao_encontrada"

        # ── 8. Tentar baixar o XML diretamente ──
        link_xml = self._page.query_selector(_SEL_LINK_XML)
        if link_xml:
            return self._baixar_xml_direto(chave, pasta_saida, link_xml)

        # ── 9. Portal só mostra resumo visual — salvar como evidência ──
        return self._salvar_resumo(chave, pasta_saida, painel_html, painel_texto)

    def _baixar_xml_direto(self, chave: str, pasta_saida: str, link_el) -> str:
        """
        Usa download via 'expect_download' do Playwright para capturar o
        arquivo XML que o portal entrega via link de download.
        """
        try:
            xml_path = os.path.join(pasta_saida, f"NFe_{chave}.xml")
            with self._page.expect_download(timeout=30_000) as dl_info:
                link_el.click()
            download = dl_info.value
            download.save_as(xml_path)
            return "sucesso_xml"
        except Exception as e:
            log.warning("Erro no download do XML da chave %s: %s", chave, e)
            return "erro_download_xml"

    def _salvar_resumo(
        self,
        chave: str,
        pasta_saida: str,
        html: str,
        texto: str,
    ) -> str:
        """
        Quando o portal não oferece download do XML, salva o HTML do painel
        como arquivo `.html` para auditoria.
        """
        try:
            html_path = os.path.join(pasta_saida, f"Resumo_{chave}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            self._on_prog(
                f"[Portal SEFAZ]   [INFO] Sem link de XML — resumo salvo "
                f"({len(texto)} chars)."
            )
            return "sucesso_resumo"
        except Exception as e:
            log.warning("Erro ao salvar resumo da chave %s: %s", chave, e)
            return "erro_resumo"

    # ── Ciclo de vida do browser ─────────────────────────────────────────────

    def _iniciar_browser(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()

        # Tenta usar o Microsoft Edge instalado no Windows (sem download extra).
        # Se não tiver, usa o Chromium embarcado do Playwright.
        try:
            self._browser = self._pw.chromium.launch(
                channel="msedge",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            self._on_prog("[Portal SEFAZ] Usando Microsoft Edge.")
        except Exception:
            self._browser = self._pw.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            self._on_prog("[Portal SEFAZ] Usando Chromium.")

        context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            accept_downloads=True,
        )
        self._page = context.new_page()

        # Ocultar sinais de automação para evitar fingerprinting
        self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    def _fechar_browser(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._page    = None
        self._pw      = None

    # ── Utilidades ───────────────────────────────────────────────────────────

    def _capturar_screenshot(self, chave: str, motivo: str):
        """Salva screenshot de debug em ~/.HebronAutoXML/screenshots/"""
        try:
            diag_dir = os.path.join(
                os.path.expanduser("~"), ".HebronAutoXML", "screenshots"
            )
            os.makedirs(diag_dir, exist_ok=True)
            ts   = int(time.time())
            path = os.path.join(diag_dir, f"{motivo}_{chave[:20]}_{ts}.png")
            self._page.screenshot(path=path)
            self._on_prog(f"[Portal SEFAZ]   [SCREENSHOT] {path}")
        except Exception:
            pass

    @staticmethod
    def _verificar_playwright():
        """Garante que o playwright está instalado antes de tentar usar."""
        try:
            import playwright  # noqa: F401
        except ImportError:
            raise PlaywrightIndisponivel(
                "A biblioteca 'playwright' nao esta instalada. "
                "Execute: pip install playwright && playwright install chromium"
            )
