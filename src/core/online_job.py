import os
import time
from datetime import datetime
from typing import Callable

from src.core.parser_excel import ler_coluna_b
from src.core.key_validator import classificar_chaves
from src.core.deduplicador import remover_duplicadas
from src.core.classificador_tipo import classificar_por_modelo
from src.core.cert_manager import CertManager, CertificadoInvalidoError
from src.core.sefaz_nfe import consultar_nfe_chave
from src.core.sefaz_cte import consultar_cte_chave
from src.io_reports.report_writer import gerar_relatorio_excel
from src.io_reports.zipper import gerar_zip_arquivos

def iniciar_download_sefaz(
    caminho_excel: str,
    caminho_pfx: str,
    senha_pfx: str,
    pasta_output_raiz: str,
    ambiente: str = "producao",
    on_progresso: Callable = None
) -> dict:
    
    if not on_progresso:
        on_progresso = lambda msg, atual=None, total=None: None
        
    on_progresso("Validando Certificado Digital (A1)...")
    try:
        cert_mgr = CertManager(caminho_pfx, senha_pfx)
        cert_mgr.verificar_vigencia()
        cnpj_base = cert_mgr.get_cnpj()
    except CertificadoInvalidoError as e:
        raise Exception(f"Erro no Certificado: {str(e)}")
        
    on_progresso(f"Certificado OK. CNPJ Extraído: {cnpj_base}")
    
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    pasta_sucesso = os.path.join(pasta_output_raiz, f"Processados_Online_{time_str}")
    sub_pasta_xml = os.path.join(pasta_sucesso, "xmls")
    os.makedirs(sub_pasta_xml, exist_ok=True)
    
    on_progresso("Lendo chaves do Excel...")
    chaves_impuras = ler_coluna_b(caminho_excel)
    chaves_validas, chaves_invalidas = classificar_chaves(chaves_impuras)
    chaves_unicas, chaves_duplicadas = remover_duplicadas(chaves_validas)
    
    on_progresso("Classificando por tipo de modelo...")
    chaves_nfe, chaves_cte, chaves_desconhecidas = classificar_por_modelo(chaves_unicas)
    
    registros_relatorio = []
    
    # Registra anomalias pré-processamento
    for chave in chaves_duplicadas:
        registros_relatorio.append({'chave': chave, 'status': 'duplicada', 'observacao': 'Chave ignorada, informada duplicada no excel.', 'arquivo_xml': ''})
    for chave in chaves_invalidas:
        registros_relatorio.append({'chave': chave, 'status': 'invalida_nao_padrao', 'observacao': 'Formato recusado na base local (Qtd dígitos).', 'arquivo_xml': ''})
    for chave in chaves_desconhecidas:
        registros_relatorio.append({'chave': chave, 'status': 'nao_suportado', 'observacao': 'Modelo (21-22) diferente de NFe(55) e CTe(57).', 'arquivo_xml': ''})
        
    total_validas = len(chaves_nfe) + len(chaves_cte)
    baixadas_com_sucesso = 0
    
    if total_validas > 0:
        with cert_mgr.pem_temporario() as (cert_path, key_path):
            total_processadas = 0
            
            # --- LOOP DE NOTA FISCAL (NFE) ---
            for chave in chaves_nfe:
                total_processadas += 1
                on_progresso(f"[NFe] Baixando {total_processadas} de {total_validas} (Chave: {chave})... Aguarde.", total_processadas, total_validas)
                
                try:
                    cert_mgr.verificar_vigencia()
                except CertificadoInvalidoError as e:
                    registros_relatorio.append({'chave': chave, 'status': 'certificado_expirado', 'observacao': str(e), 'arquivo_xml': ''})
                    break
                    
                uf_autor = chave[:2]
                
                resp = consultar_nfe_chave(cert_path, key_path, uf_autor, cnpj_base, chave, ambiente)
                
                if resp['status'] == 'sucesso_xml':
                    caminho_xml = os.path.join(sub_pasta_xml, f"NFe_{chave}.xml")
                    with open(caminho_xml, 'w', encoding='utf-8') as f:
                        f.write(resp['conteudo'])
                    registros_relatorio.append({'chave': chave, 'status': 'baixada_ok', 'observacao': 'Download validado completo Sefaz.', 'arquivo_xml': os.path.basename(caminho_xml)})
                    baixadas_com_sucesso += 1
                else:
                    registros_relatorio.append({'chave': chave, 'status': resp['status'], 'observacao': resp.get('mensagem', ''), 'arquivo_xml': ''})
                    
                if total_processadas < total_validas:
                    time.sleep(1.0) # Taxa de contorno antifraude da SEFAZ
                
            # --- LOOP DE CONHECIMENTO (CTE) ---
            for chave in chaves_cte:
                total_processadas += 1
                on_progresso(f"[CTe] Baixando {total_processadas} de {total_validas} (Chave: {chave})... Aguarde.", total_processadas, total_validas)
                
                try:
                    cert_mgr.verificar_vigencia()
                except CertificadoInvalidoError as e:
                    registros_relatorio.append({'chave': chave, 'status': 'certificado_expirado', 'observacao': str(e), 'arquivo_xml': ''})
                    break
                
                uf_autor = chave[:2]
                
                resp = consultar_cte_chave(cert_path, key_path, uf_autor, cnpj_base, chave, ambiente)
                
                if resp['status'] == 'sucesso_xml':
                    caminho_xml = os.path.join(sub_pasta_xml, f"CTe_{chave}.xml")
                    with open(caminho_xml, 'w', encoding='utf-8') as f:
                        f.write(resp['conteudo'])
                    registros_relatorio.append({'chave': chave, 'status': 'baixada_ok', 'observacao': 'Download CTe concluído (distDFeInt).', 'arquivo_xml': os.path.basename(caminho_xml)})
                    baixadas_com_sucesso += 1
                else:
                    registros_relatorio.append({'chave': chave, 'status': resp['status'], 'observacao': resp.get('mensagem', ''), 'arquivo_xml': ''})
                
                if total_processadas < total_validas:
                    time.sleep(1.0)
                
    on_progresso("Finalizando relatórios...")
    caminho_relatorio = os.path.join(pasta_sucesso, "relatorio_download_online.xlsx")
    gerar_relatorio_excel(caminho_relatorio, registros_relatorio)
    
    if baixadas_com_sucesso > 0:
        on_progresso("Compactando...", total_validas, total_validas)
        caminho_zip = os.path.join(pasta_sucesso, "baixados_sefaz_zip")
        gerar_zip_arquivos(sub_pasta_xml, caminho_zip)
        
    on_progresso("Concluído", total_validas, total_validas)

    return {
        "diretorio_saida": pasta_sucesso,
        "total_lidas": len(chaves_impuras),
        "total_invalidas": len(chaves_invalidas) + len(chaves_desconhecidas),
        "total_duplicadas": len(chaves_duplicadas),
        "total_unicas": len(chaves_unicas),
        "total_encontradas": baixadas_com_sucesso
    }
