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
from src.core.sefaz_distnsu import baixar_lote_nsu
from src.core.sefaz_cte import consultar_cte_chave
from src.core.sefaz_tools import obter_chave_interna, descompactar_base64_zip
from src.core.nsu_cache import get_cached_nsu, save_nsu
from src.core.checkpoint_manager import (
    get_downloaded, mark_downloaded, mark_blocked,
    get_cooldown_remaining, clear_blocked, try_recover_xml
)
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
    on_progresso(f"🔍 [DEBUG] Iniciando análise para o CNPJ: {cnpj_base}")
    
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
            
            # --- FASE 1: LOTE DE NOTA FISCAL (distNSU) ---
            chaves_nfe_pendentes = list(chaves_nfe)
            
            if chaves_nfe_pendentes:
                uf_autor_nsu, uf_raw = cert_mgr.get_uf()
                on_progresso(f"🔍 [DEBUG] Campo de UF lido do certificado: '{uf_raw}' → Mapeado para Código IBGE: {uf_autor_nsu or 'NÃO ENCONTRADO (tag cUFAutor será omitida no XML)'}")
                on_progresso(f"[Fase 1] Consultando notas recentes em Lote (NSU) na Sefaz (UF Origem: {uf_autor_nsu or 'Nenhum'})...")
                
                ult_nsu = get_cached_nsu(cnpj_base, ambiente)
                on_progresso(f"🔍 [DEBUG] ultNSU recuperado da memória (cache): {ult_nsu}")
                max_nsu = str(int(ult_nsu) + 1)
                tentativas = 0
                lotes_sem_match = 0
                
                while int(ult_nsu) < int(max_nsu) and tentativas < 500 and chaves_nfe_pendentes:
                    resp_nsu = baixar_lote_nsu(cert_path, key_path, uf_autor_nsu, cnpj_base, ult_nsu, ambiente)
                    
                    if resp_nsu.get('status') in ('vazio', 'rejeitado_656', 'erro_rede', 'erro_soap'):
                        motivo = resp_nsu.get('mensagem', 'Nenhum documento retornado na malha')
                        on_progresso(f"[Fase 1] Lote interrompido/vazio: {resp_nsu.get('status')} — {motivo}")
                        if resp_nsu.get('status') == 'rejeitado_656':
                            registros_relatorio.append({'chave': 'LOTE_NSU', 'status': 'aviso', 'observacao': 'Fase 1 interrompida por atingimento do rate-limit.', 'arquivo_xml': ''})
                        break
                        
                    ult_nsu = resp_nsu.get('ultNSU', ult_nsu)
                    save_nsu(cnpj_base, ambiente, ult_nsu)
                    max_nsu = resp_nsu.get('maxNSU', max_nsu)
                    
                    encontradas_neste_lote = 0
                    nfes_no_lote = 0
                    for doc in resp_nsu.get('docs', []):
                        if 'procNFe' in doc.get('schema', ''):
                            nfes_no_lote += 1
                            try:
                                xml_str = descompactar_base64_zip(doc['content_b64'])
                                chave_extraida = obter_chave_interna(xml_str)
                                
                                if chave_extraida in chaves_nfe_pendentes:
                                    caminho_xml = os.path.join(sub_pasta_xml, f"NFe_{chave_extraida}.xml")
                                    with open(caminho_xml, 'w', encoding='utf-8') as f:
                                        f.write(xml_str)
                                    registros_relatorio.append({'chave': chave_extraida, 'status': 'baixada_ok', 'observacao': 'Sucesso via Lote (distNSU).', 'arquivo_xml': os.path.basename(caminho_xml)})
                                    baixadas_com_sucesso += 1
                                    chaves_nfe_pendentes.remove(chave_extraida)
                                    encontradas_neste_lote += 1
                            except Exception:
                                pass
                    
                    if encontradas_neste_lote > 0:
                        lotes_sem_match = 0
                    else:
                        lotes_sem_match += 1
                        
                    if lotes_sem_match >= 50:
                        on_progresso("[Fase 1] ⚡ Interrompendo varredura — 50 lotes sem encontrar chaves pendentes. Acelerando processo automático...")
                        break
                    
                    pct = int((int(ult_nsu) / max(int(max_nsu), 1)) * 100)
                    msg_encontradas = f" ✅ +{encontradas_neste_lote} encontradas!" if encontradas_neste_lote else ""
                    on_progresso(f"[Fase 1] NSU {ult_nsu}/{max_nsu} ({pct}%) | {nfes_no_lote} NFes no lote | Pendentes: {len(chaves_nfe_pendentes)}{msg_encontradas}")
                    tentativas += 1
                    time.sleep(0.5)
                    
            # --- FASE 2: LOOP INDIVIDUAL (NFe consChNFe Fallback) ---
            # Com checkpoint: retoma de onde parou, skipando chaves já baixadas.
            chaves_ja_baixadas = get_downloaded(cnpj_base, ambiente)
            chaves_puladas_ck = {c: info for c, info in chaves_ja_baixadas.items() if c in chaves_nfe_pendentes}
            chaves_fase2 = [c for c in chaves_nfe_pendentes if c not in chaves_ja_baixadas]

            # Recuperar XMLs de sessões anteriores
            if chaves_puladas_ck:
                on_progresso(f"[Fase 2] ♻️  Recuperando {len(chaves_puladas_ck)} chave(s) do checkpoint de sessões anteriores...")
                for chave_ck, info_ck in chaves_puladas_ck.items():
                    total_processadas += 1
                    arquivo_recuperado = try_recover_xml(chave_ck, info_ck, sub_pasta_xml)
                    if arquivo_recuperado:
                        on_progresso(f"[Fase 2] ✅ {chave_ck[:20]}... → arquivo copiado da sessão anterior.")
                        registros_relatorio.append({'chave': chave_ck, 'status': 'baixada_ok', 'observacao': 'Recuperado do checkpoint (sessão anterior).', 'arquivo_xml': arquivo_recuperado})
                        baixadas_com_sucesso += 1
                    else:
                        # Arquivo original foi movido/deletado — precisa re-baixar
                        on_progresso(f"[Fase 2] ⚠️  Arquivo anterior não encontrado para {chave_ck[:20]}... — adicionando para re-download.")
                        chaves_fase2.append(chave_ck)

            # Verificar cooldown ativo de execução anterior
            cooldown_secs = get_cooldown_remaining(cnpj_base, ambiente)
            if cooldown_secs > 0 and chaves_fase2:
                mins_cd, secs_cd = divmod(cooldown_secs, 60)
                on_progresso(f"[Fase 2] ⏱️  Rate-limit SEFAZ ativo — {mins_cd}min {secs_cd}s restantes.")
                on_progresso(f"[Fase 2] {len(chaves_fase2)} chave(s) pendentes. Re-execute o programa quando o tempo acabar.")
                for c in chaves_fase2:
                    total_processadas += 1
                    registros_relatorio.append({'chave': c, 'status': 'aguardando_cooldown', 'observacao': f'Rate-limit SEFAZ ativo. Re-execute em ~{mins_cd}min {secs_cd}s.', 'arquivo_xml': ''})
            else:
                # Cooldown expirou ou nunca foi bloqueado: limpar flag e processar
                clear_blocked(cnpj_base, ambiente)

                for idx, chave in enumerate(chaves_fase2):
                    total_processadas += 1
                    on_progresso(f"[Fase 2] Buscando NFe avulsa: {chave} ({len(chaves_fase2) - idx} restantes)...", total_processadas, total_validas)

                    try:
                        cert_mgr.verificar_vigencia()
                    except CertificadoInvalidoError as e:
                        registros_relatorio.append({'chave': chave, 'status': 'certificado_expirado', 'observacao': str(e), 'arquivo_xml': ''})
                        break

                    resp = consultar_nfe_chave(cert_path, key_path, cnpj_base, chave, ambiente)

                    if resp['status'] == 'sucesso_xml':
                        caminho_xml = os.path.join(sub_pasta_xml, f"NFe_{chave}.xml")
                        with open(caminho_xml, 'w', encoding='utf-8') as f:
                            f.write(resp['conteudo'])
                        registros_relatorio.append({'chave': chave, 'status': 'baixada_ok', 'observacao': 'Download FASE 2 individual validado.', 'arquivo_xml': os.path.basename(caminho_xml)})
                        baixadas_com_sucesso += 1
                        mark_downloaded(cnpj_base, ambiente, chave, caminho_xml)  # ← Salva no checkpoint

                    elif resp['status'] == 'rejeitado_656':
                        mark_blocked(cnpj_base, ambiente)  # ← Registra bloqueio com timestamp
                        pendentes_restantes = len(chaves_fase2) - idx - 1
                        on_progresso(f"[Fase 2] ⛔ Rate-limit SEFAZ (656). {pendentes_restantes} chave(s) pendentes. Re-execute em ~1 hora (checkpoint salvo).")
                        registros_relatorio.append({'chave': chave, 'status': 'bloqueado_sefaz', 'observacao': f'Rate-limit SEFAZ (656). {pendentes_restantes} chave(s) pendentes. Re-execute em ~1h.', 'arquivo_xml': ''})
                        break

                    elif resp['status'] == 'sucesso_resumo':
                        registros_relatorio.append({'chave': chave, 'status': 'sucesso_resumo', 'observacao': resp.get('mensagem', ''), 'arquivo_xml': ''})

                    else:
                        registros_relatorio.append({'chave': chave, 'status': resp['status'], 'observacao': resp.get('mensagem', ''), 'arquivo_xml': ''})

                    if idx < len(chaves_fase2) - 1:
                        for s in range(3, 0, -1):
                            on_progresso(f"⏳ Aguardando {s}s de resfriamento...", total_processadas, total_validas)
                            time.sleep(1.0)
                
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
