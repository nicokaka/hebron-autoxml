import os
import sys
import time

# Forcar UTF-8 no terminal Windows (evita UnicodeEncodeError com emojis)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

# Setup mock key
MOCK_CHAVE = "26260400446820000101550250000004251000014685"

def run_test():
    print("Iniciando Teste Playwright com SEFAZ...")
    with sync_playwright() as p:
        # Abrir navegador com interface vísivel (headed)
        # channel='msedge' ajuda a passar por deteccao ou fallback para default
        browser = p.chromium.launch(headless=False) 
        
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        
        print(f"Navegando para o portal e injetando chave: {MOCK_CHAVE}...")
        url = "https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx?tipoConsulta=resumo&tipoConteudo=7PhJ+gAVw2g="
        page.goto(url, wait_until="domcontentloaded")
        
        # Preencher a chave
        # O subagent achou esse seletor: #ctl00_ContentPlaceHolder1_txtChaveAcessoResumo
        try:
            page.fill("#ctl00_ContentPlaceHolder1_txtChaveAcessoResumo", MOCK_CHAVE)
            print("[OK] Chave preenchida.")
        except Exception as e:
            print("[ERRO] Falha ao preencher chave:", e)
            
        print("\n[AGUARDANDO] CAPTCHA: resolva na janela do navegador e clique em 'Continuar'.")
        print("Esperando carregamento da proxima pagina (timeout: 2 min)...\n")
        
        # Aguardar ate que a página mude ou um elemento de resultado apareça
        try:
            # Espera ate o elemento de id 'conteudo' aparecer (tela do XML) ou timeout de 120s
            page.wait_for_selector("#ctl00_ContentPlaceHolder1_upResumo", timeout=120000)
            print("[OK] CAPTCHA resolvido e pagina carregada!")
            
            time.sleep(2)
            resumo_texto = page.locator("#ctl00_ContentPlaceHolder1_upResumo").inner_text()
            print("=== RESUMO ENCONTRADO ===")
            print(resumo_texto[:500])
            print("...")
            
            page.screenshot(path="scratch/teste_playwright_sucesso.png")
            print("[OK] Screenshot salvo em scratch/teste_playwright_sucesso.png")
            
        except Exception as e:
            print(f"[ERRO] Falha ou Timeout: {e}")
            page.screenshot(path="scratch/teste_playwright_timeout.png")
            print("[INFO] Screenshot de timeout salvo em scratch/teste_playwright_timeout.png")
            
        print("\nFechando navegador em 5 segundos...")
        time.sleep(5)
        browser.close()

if __name__ == "__main__":
    run_test()
