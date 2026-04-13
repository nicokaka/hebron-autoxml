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
from src.core.sefaz_tools import obter_chave_interna, descompactar_base64_zip
from src.core.nsu_cache import get_cached_nsu, save_nsu
from src.core.triagem import classificar_entrada_saida, calcular_eta
from src.core.sefaz_manifestacao import enviar_manifestacao
from src.core.portal_scraper import SefazPortalScraper, PlaywrightIndisponivel
from src.core.checkpoint_manager import (
    get_downloaded, mark_downloaded, mark_blocked,
    get_cooldown_remaining, clear_blocked, try_recover_xml,
    cleanup_old_cache
)
from src.io_reports.report_writer import gerar_relatorio_excel
from src.io_reports.zipper import gerar_zip_arquivos


def iniciar_download_sefaz(
    caminho_excel: str,
    caminho_pfx: str,
    senha_pfx: str,
    pasta_output_raiz: str,
    ambiente: str = "producao",
    on_progresso: Callable = None,
    on_alerta_saidas: Callable = None,   # callback para popup de alerta vermelho
    captcha_api_key: str = "",
) -> dict:
    """
    Orquestra o download de XMLs da SEFAZ em 5 passos:

    Passo 0: Triagem Offline    — Classifica entradas vs. saídas (0 requisições)
    Passo 1: Manifestação       — Ciência da Operação em lote para as entradas
    Passo 2: Delay 240s         — SEFAZ processa e libera os XMLs na fila
    Passo 3: distNSU            — Varredura em lote (50 docs/req)
    Passo 4: Fallback consChNFe — Somente saídas/restantes, 180s por chave

    Args:
        on_alerta_saidas: Se fornecido, chamado com (eta_dict) quando >80% são saídas.
                          Deve retornar False para cancelar a execução, True para continuar.
    """
    if not on_progresso:
        on_progresso = lambda msg, atual=None, total=None: None

    # ─── Limpeza de cache antigo ────────────────────────────────────────────
    cleanup_old_cache()

    # ─── Validação do Certificado ────────────────────────────────────────────
    on_progresso("Validando Certificado Digital (A1)...")
    try:
        cert_mgr = CertManager(caminho_pfx, senha_pfx)
        cert_mgr.verificar_vigencia()
        cnpj_base = cert_mgr.get_cnpj()
    except CertificadoInvalidoError as e:
        raise Exception(f"Erro no Certificado: {str(e)}")

    on_progresso(f"Certificado OK. CNPJ Extraído: {cnpj_base}")

    # ─── Criação de Pastas ───────────────────────────────────────────────────
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    pasta_sucesso = os.path.join(pasta_output_raiz, f"Processados_Online_{time_str}")
    sub_pasta_xml = os.path.join(pasta_sucesso, "xmls")
    os.makedirs(sub_pasta_xml, exist_ok=True)

    # ─── Leitura e classificação do Excel ───────────────────────────────────
    on_progresso("Lendo chaves do Excel...")
    chaves_impuras = ler_coluna_b(caminho_excel)
    chaves_validas, chaves_invalidas = classificar_chaves(chaves_impuras)
    chaves_unicas, chaves_duplicadas = remover_duplicadas(chaves_validas)

    on_progresso("Classificando por tipo de modelo...")
    chaves_nfe, chaves_cte, chaves_desconhecidas = classificar_por_modelo(chaves_unicas)

    registros_relatorio = []
    for chave in chaves_duplicadas:
        registros_relatorio.append({'chave': chave, 'status': 'duplicada', 'observacao': 'Chave ignorada, informada duplicada no excel.', 'arquivo_xml': ''})
    for chave in chaves_invalidas:
        registros_relatorio.append({'chave': chave, 'status': 'invalida_nao_padrao', 'observacao': 'Formato recusado na base local (Qtd dígitos).', 'arquivo_xml': ''})
    for chave in chaves_desconhecidas:
        registros_relatorio.append({'chave': chave, 'status': 'nao_suportado', 'observacao': 'Modelo (21-22) diferente de NFe(55) e CTe(57).', 'arquivo_xml': ''})

    # CT-e ainda usa o endpoint próprio — não mistura com o fallback NFe
    # Registra CT-e como "suporte futuro" por enquanto
    for chave in chaves_cte:
        registros_relatorio.append({'chave': chave, 'status': 'ignorado_cte', 'observacao': 'CT-e: suporte via CTeDistribuicaoDFe (v3.1). Use endpoint CTe separado.', 'arquivo_xml': ''})

    if chaves_cte:
        on_progresso(f"ℹ️ {len(chaves_cte)} chave(s) CT-e registradas no relatório (endpoint separado na v3.1).")

    total_validas = len(chaves_nfe)
    baixadas_com_sucesso = 0
    total_processadas = 0

    if total_validas == 0:
        on_progresso("Nenhuma chave NFe válida encontrada. Encerrando.")
    else:
        # ═══════════════════════════════════════════════════════════════════════
        # PASSO 0: TRIAGEM OFFLINE — classificar entradas vs. saídas
        # ═══════════════════════════════════════════════════════════════════════
        on_progresso("─" * 50)
        on_progresso("🔍 [Passo 0] Triagem Offline das chaves...")

        entradas, saidas = classificar_entrada_saida(chaves_nfe, [], cnpj_base)
        eta = calcular_eta(len(entradas), len(saidas))

        on_progresso(
            f"   📥 Entradas (destinatário): {eta['entradas']} chave(s) — via Manifestação"
        )
        on_progresso(
            f"   📤 Saídas (emitente):       {eta['saidas']} chave(s) — via Fallback (180s/chave)"
        )

        # ─── Alerta Vermelho: >80% de saídas ────────────────────────────────
        if eta['alerta_vermelho'] and on_alerta_saidas:
            continuar = on_alerta_saidas(eta)
            if not continuar:
                on_progresso("❌ Operação cancelada pelo usuário.")
                return {
                    "diretorio_saida": pasta_sucesso,
                    "total_lidas": len(chaves_impuras),
                    "total_invalidas": len(chaves_invalidas) + len(chaves_desconhecidas),
                    "total_duplicadas": len(chaves_duplicadas),
                    "total_unicas": len(chaves_unicas),
                    "total_encontradas": 0,
                }
        elif eta['alerta_vermelho']:
            horas = eta['total_horas']
            on_progresso(
                f"⚠️  AVISO: {eta['pct_saidas']}% das notas são saídas. "
                f"ETA total: ~{horas}h. O programa continuará em modo segurança."
            )

        with cert_mgr.pem_temporario() as (cert_path, key_path):

            # ═══════════════════════════════════════════════════════════════════
            # PASSO 1: MANIFESTAÇÃO DE DESTINATÁRIO (Entradas)
            # ═══════════════════════════════════════════════════════════════════
            chaves_nfe_pendentes = list(chaves_nfe)   # Todas as NFe — distNSU vai cruzar
            resultado_manifestacao = {}

            if entradas:
                on_progresso("─" * 50)
                on_progresso(f"📋 [Passo 1] Manifestação — enviando Ciência da Operação para {len(entradas)} entradas...")

                try:
                    resultado_manifestacao = enviar_manifestacao(
                        cert_path, key_path, cnpj_base, entradas, ambiente,
                        on_progresso=lambda msg: on_progresso(msg)
                    )
                    sucessos_manif = sum(1 for v in resultado_manifestacao.values() if v in ("135", "573"))
                    on_progresso(f"✅ [Passo 1] Manifestação concluída: {sucessos_manif}/{len(entradas)} registradas na SEFAZ.")
                except Exception as e:
                    sucessos_manif = 0
                    on_progresso(f"⚠️ [Passo 1] Erro na Manifestação: {e}. Continuando sem ela...")

                # ═══════════════════════════════════════════════════════════════
                # PASSO 2: DELAY — SEFAZ processa e libera os XMLs na fila
                # ═══════════════════════════════════════════════════════════════
                if sucessos_manif > 0:
                    on_progresso("─" * 50)
                    on_progresso("⏳ [Passo 2] Aguardando SEFAZ liberar XMLs na fila (4 minutos)...")
                    for s in range(240, 0, -1):
                        mins_r, secs_r = divmod(s, 60)
                        on_progresso(f"   ⏳ {mins_r}min {secs_r:02d}s restantes...")
                        time.sleep(1)
                    on_progresso("✅ [Passo 2] Delay concluído. Abrindo a torneira do distNSU...")
                else:
                    on_progresso("─" * 50)
                    on_progresso("⏩ [Passo 2] Pulando delay — nenhuma manifestação registrada. Indo direto ao distNSU/Fallback.")
            else:
                on_progresso("ℹ️ [Passo 1] Sem entradas para manifestar. Pulando para distNSU.")

            # ═══════════════════════════════════════════════════════════════════
            # PASSO 3: distNSU — Varredura em lote (50 docs/req)
            # ═══════════════════════════════════════════════════════════════════
            on_progresso("─" * 50)
            uf_autor_nsu, uf_raw = cert_mgr.get_uf()
            on_progresso(f"🔍 [Passo 3] distNSU — UF certificado: '{uf_raw}' → IBGE: {uf_autor_nsu or 'Não encontrada (tag omitida)'}. Varrendo lotes...")

            ult_nsu = get_cached_nsu(cnpj_base, ambiente)
            on_progresso(f"   📌 ultNSU recuperado do cache: {ult_nsu}")
            max_nsu = str(int(ult_nsu) + 1)
            tentativas = 0
            lotes_sem_match = 0

            while int(ult_nsu) < int(max_nsu) and tentativas < 500 and chaves_nfe_pendentes:
                resp_nsu = baixar_lote_nsu(cert_path, key_path, uf_autor_nsu, cnpj_base, ult_nsu, ambiente)

                if resp_nsu.get('status') in ('vazio', 'rejeitado_656', 'erro_rede', 'erro_soap'):
                    motivo = resp_nsu.get('mensagem', 'Nenhum documento retornado')
                    on_progresso(f"[Passo 3] Lote interrompido: {resp_nsu.get('status')} — {motivo}")
                    if resp_nsu.get('status') == 'rejeitado_656':
                        registros_relatorio.append({'chave': 'LOTE_NSU', 'status': 'aviso', 'observacao': 'Fase distNSU interrompida por rate-limit.', 'arquivo_xml': ''})
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
                                mark_downloaded(cnpj_base, ambiente, chave_extraida, caminho_xml)
                                registros_relatorio.append({'chave': chave_extraida, 'status': 'baixada_ok', 'observacao': 'Sucesso via distNSU (Lote).', 'arquivo_xml': os.path.basename(caminho_xml)})
                                baixadas_com_sucesso += 1
                                total_processadas += 1
                                chaves_nfe_pendentes.remove(chave_extraida)
                                encontradas_neste_lote += 1
                        except Exception as e_xml:
                            on_progresso(f"[Passo 3] ⚠️ Erro ao processar doc NSU {doc.get('NSU','?')}: {e_xml}")

                if encontradas_neste_lote > 0:
                    lotes_sem_match = 0
                else:
                    lotes_sem_match += 1

                if lotes_sem_match >= 150:
                    on_progresso("[Passo 3] ⚡ 150 lotes consecutivos sem match — encerrando varredura.")
                    break

                pct = int((int(ult_nsu) / max(int(max_nsu), 1)) * 100)
                msg_enc = f" ✅ +{encontradas_neste_lote}" if encontradas_neste_lote else ""
                on_progresso(f"[Passo 3] NSU {ult_nsu}/{max_nsu} ({pct}%) | {nfes_no_lote} NFes | Pendentes: {len(chaves_nfe_pendentes)}{msg_enc}", total_processadas, total_validas)
                tentativas += 1
                time.sleep(0.5)

            # ─── Mensagem de transição pós-distNSU ──────────────────────────
            on_progresso("─" * 50)
            if baixadas_com_sucesso > 0 and chaves_nfe_pendentes:
                pct_ok = round(baixadas_com_sucesso / total_validas * 100)
                eta_fallback_min = round(len(chaves_nfe_pendentes) * 15 / 60, 1)
                on_progresso(
                    f"{baixadas_com_sucesso} nota(s) ({pct_ok}%) baixadas com sucesso! Ja podem ser usadas."
                )
                on_progresso(
                    f"[!] {len(chaves_nfe_pendentes)} nota(s) restritas - portal SEFAZ (captcha). "
                    f"ETA: ~{eta_fallback_min} min. Pode minimizar a janela!"
                )
            elif baixadas_com_sucesso > 0 and not chaves_nfe_pendentes:
                on_progresso(f"🎉 Todas as {baixadas_com_sucesso} notas foram baixadas pelo distNSU! Excelente.")

            # ═══════════════════════════════════════════════════════════════════
            # PASSO 4: FALLBACK consChNFe (Saídas + Pendentes, 180s por chave)
            # ═══════════════════════════════════════════════════════════════════
            # Checkpoint: skipa chaves já baixadas em sessões anteriores
            chaves_ja_baixadas = get_downloaded(cnpj_base, ambiente)
            chaves_puladas_ck = {c: info for c, info in chaves_ja_baixadas.items() if c in chaves_nfe_pendentes}
            chaves_fallback = [c for c in chaves_nfe_pendentes if c not in chaves_ja_baixadas]

            # Recuperar XMLs de sessões anteriores
            if chaves_puladas_ck:
                on_progresso(f"[Passo 4] ♻️  Recuperando {len(chaves_puladas_ck)} chave(s) do checkpoint de sessões anteriores...")
                for chave_ck, info_ck in chaves_puladas_ck.items():
                    total_processadas += 1
                    arquivo_recuperado = try_recover_xml(chave_ck, info_ck, sub_pasta_xml)
                    if arquivo_recuperado:
                        on_progresso(f"[Passo 4] ✅ {chave_ck[:20]}... → copiado da sessão anterior.")
                        registros_relatorio.append({'chave': chave_ck, 'status': 'baixada_ok', 'observacao': 'Recuperado do checkpoint (sessão anterior).', 'arquivo_xml': arquivo_recuperado})
                        baixadas_com_sucesso += 1
                    else:
                        on_progresso(f"[Passo 4] ⚠️  Arquivo anterior não encontrado para {chave_ck[:20]}... — re-download.")
                        chaves_fallback.append(chave_ck)

            # Verificar cooldown ativo
            cooldown_secs = get_cooldown_remaining(cnpj_base, ambiente)
            if cooldown_secs > 0 and chaves_fallback:
                mins_cd, secs_cd = divmod(cooldown_secs, 60)
                on_progresso(f"[Passo 4] ⏱️  Rate-limit SEFAZ ativo — {mins_cd}min {secs_cd}s restantes.")
                on_progresso(f"[Passo 4] {len(chaves_fallback)} chave(s) pendentes. Re-execute quando o cooldown expirar.")
                for c in chaves_fallback:
                    total_processadas += 1
                    registros_relatorio.append({'chave': c, 'status': 'aguardando_cooldown', 'observacao': f'Rate-limit ativo. Re-execute em ~{mins_cd}min {secs_cd}s.', 'arquivo_xml': ''})
            elif chaves_fallback:
                clear_blocked(cnpj_base, ambiente)

                # ═══════════════════════════════════════════════════════════════
                # PASSO 4A: PLAYWRIGHT SCRAPER (Portal Web — sem rate-limit)
                # ═══════════════════════════════════════════════════════════════
                chaves_para_legado = list(chaves_fallback)  # fallback segurança

                try:
                    on_progresso("─" * 50)
                    on_progresso(
                        f"[Passo 4] 🌐 Portal SEFAZ (Playwright): "
                        f"{len(chaves_fallback)} chave(s) — sem rate-limit."
                    )
                    scraper = SefazPortalScraper(on_progresso=on_progresso, captcha_api_key=captcha_api_key)
                    resultados_pw = scraper.baixar_xmls(chaves_fallback, sub_pasta_xml)

                    # Processar resultados do Playwright
                    chaves_para_legado = []
                    chaves_processadas_pw = set()

                    for chave_pw, status_pw in resultados_pw.items():
                        chaves_processadas_pw.add(chave_pw)
                        if status_pw == "sucesso_xml":
                            total_processadas += 1   # conta 1x: resultado definitivo
                            caminho_xml = os.path.join(sub_pasta_xml, f"NFe_{chave_pw}.xml")
                            baixadas_com_sucesso += 1
                            mark_downloaded(cnpj_base, ambiente, chave_pw, caminho_xml)
                            registros_relatorio.append({
                                'chave': chave_pw, 'status': 'baixada_ok',
                                'observacao': 'Download via Portal SEFAZ (Playwright).',
                                'arquivo_xml': os.path.basename(caminho_xml)
                            })
                        elif status_pw == "sucesso_resumo":
                            total_processadas += 1   # conta 1x: resultado definitivo
                            registros_relatorio.append({
                                'chave': chave_pw, 'status': 'sucesso_resumo',
                                'observacao': 'Portal retornou apenas resumo visual.',
                                'arquivo_xml': ''
                            })
                        elif status_pw == "chave_nao_encontrada":
                            total_processadas += 1   # conta 1x: resultado definitivo
                            registros_relatorio.append({
                                'chave': chave_pw, 'status': 'chave_nao_encontrada',
                                'observacao': 'Chave nao encontrada no portal SEFAZ.',
                                'arquivo_xml': ''
                            })
                        else:
                            # captcha_timeout/invalido/erro -> legado vai contar ao processar
                            chaves_para_legado.append(chave_pw)

                    # Chaves que o scraper nao chegou a processar
                    for chave_nproc in chaves_fallback:
                        if chave_nproc not in chaves_processadas_pw:
                            chaves_para_legado.append(chave_nproc)


                except PlaywrightIndisponivel:
                    on_progresso(
                        "[Passo 4] ⚠️  Playwright não disponível. "
                        "Usando fallback WebService (180s/chave)."
                    )
                    chaves_para_legado = list(chaves_fallback)

                except Exception as e_pw:
                    on_progresso(f"[Passo 4] ⚠️  Playwright falhou ({e_pw}). WebService como segurança.")
                    chaves_para_legado = list(chaves_fallback)

                # ═══════════════════════════════════════════════════════════════
                # PASSO 4B: LEGADO consChNFe (backup — 180s por chave)
                # ═══════════════════════════════════════════════════════════════
                if chaves_para_legado:
                    on_progresso("─" * 50)
                    on_progresso(
                        f"[Passo 4B] Fallback WebService: "
                        f"{len(chaves_para_legado)} chave(s) | 180s/chave."
                    )


                for idx, chave in enumerate(chaves_para_legado):
                    total_processadas += 1
                    on_progresso(
                        f"[Passo 4B] consChNFe {idx + 1}/{len(chaves_para_legado)}: {chave}...",
                        total_processadas, total_validas
                    )

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
                        registros_relatorio.append({'chave': chave, 'status': 'baixada_ok', 'observacao': 'Download via Fallback consChNFe (WebService).', 'arquivo_xml': os.path.basename(caminho_xml)})
                        baixadas_com_sucesso += 1
                        mark_downloaded(cnpj_base, ambiente, chave, caminho_xml)

                    elif resp['status'] == 'rejeitado_656':
                        mark_blocked(cnpj_base, ambiente)
                        pendentes = len(chaves_para_legado) - idx - 1
                        on_progresso(f"[Passo 4B] ⛔ cStat 656. HARD STOP. {pendentes} chave(s) salvas no checkpoint. Re-execute em ~1h.")
                        registros_relatorio.append({'chave': chave, 'status': 'bloqueado_sefaz', 'observacao': f'cStat 656. Hard Stop. {pendentes} pendentes. Re-execute em ~1h.', 'arquivo_xml': ''})
                        break

                    elif resp['status'] == 'sucesso_resumo':
                        registros_relatorio.append({'chave': chave, 'status': 'sucesso_resumo', 'observacao': resp.get('mensagem', ''), 'arquivo_xml': ''})

                    else:
                        registros_relatorio.append({'chave': chave, 'status': resp['status'], 'observacao': resp.get('mensagem', ''), 'arquivo_xml': ''})

                    # Delay de 180s entre cada chave
                    if idx < len(chaves_para_legado) - 1:
                        on_progresso(f"   ⏳ Resfriamento de 3 min antes da próxima chave...", total_processadas, total_validas)
                        for s in range(180, 0, -1):
                            mins_s, secs_s = divmod(s, 60)
                            if s % 30 == 0 or s <= 10:
                                on_progresso(f"   ⏳ {mins_s}min {secs_s:02d}s restantes...", total_processadas, total_validas)
                            time.sleep(1)

                # Notificação toast ao concluir o fallback
                try:
                    from plyer import notification
                    notification.notify(
                        title="HebronAutoXML",
                        message=f"Download concluído! {baixadas_com_sucesso}/{total_validas} notas baixadas.",
                        app_name="HebronAutoXML",
                        timeout=10,
                    )
                except Exception:
                    pass   # Silencioso se plyer não disponível ou Windows bloquear

    # ─── Relatório e empacotamento ───────────────────────────────────────────
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
        "total_encontradas": baixadas_com_sucesso,
    }
