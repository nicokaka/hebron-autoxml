"""
Tester End-to-End da lógica core do HebronAutoXML v3.1.0 
Este script ignora a interface gráfica CustomTkinter para facilitar o trace das execuções em desenvolvimento local.
"""

import sys
import os
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.online_job import iniciar_download_sefaz

def print_log(msg, *args):
    print(f"[TESTE E2E] {msg}")

def testar():
    print("="*60)
    print("🚗 INICIANDO TESTADOR E2E (Sem GUI)")
    print("="*60)
    
    # ─── Configurações ──────────────────────────────────────
    # >>> IMPORTANTE: Insira aqui dados válidos de homologação/produção antes de rodar! <<<
    excel_path = r"C:\PATH\TO\SEU\EXCEL.xlsx"
    pfx_path = r"C:\PATH\TO\SEU\CERTIFICADO.pfx"
    senha_pfx = "sua_senha"
    # ────────────────────────────────────────────────────────
    
    if not os.path.exists(excel_path) or not os.path.exists(pfx_path):
        print("⚠️  AVISO: Por favor, edite os paths 'excel_path' e 'pfx_path' no script para arquivos reais antes de executar!")
        print(f"Buscando: {excel_path} e {pfx_path}")
        return

    pasta_saida = os.path.join(os.path.expanduser("~"), "Desktop", "TESTE_HOMOL")
    os.makedirs(pasta_saida, exist_ok=True)
    
    print("\n[!] Rodando orquestrador...")
    
    # O mock de popup de Saídas sempre retornará True para prosseguir
    def mock_popup_saidas(info):
        print(f"\n[POPUP SIMULADO] Alerta de saídas: {info['pct_saidas']}% são saídas. ETA: {info['eta_horas']} horas.")
        print("[POPUP SIMULADO] Acionando botão 'Prosseguir automaticamente'.\n")
        return True

    try:
        resultado = iniciar_download_sefaz(
            caminho_excel=excel_path,
            caminho_pfx=pfx_path,
            senha_pfx=senha_pfx,
            pasta_destino=pasta_saida,
            on_progresso=print_log,
            on_alerta_saidas=mock_popup_saidas,
            ambiente="producao"  # Altere para homologacao se o certificado permitir
        )
        print("\n✅ Resumo do Processamento:")
        print(resultado)
    except Exception as e:
        print(f"\n❌ Erro crítico no fluxo: {e}")

if __name__ == "__main__":
    testar()
