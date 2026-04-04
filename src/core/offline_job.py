import os
import shutil
from datetime import datetime

from src.core.parser_excel import ler_coluna_b
from src.core.key_validator import classificar_chaves
from src.core.deduplicador import remover_duplicadas
from src.core.matcher_xml import indexar_e_cruzar_xmls
from src.io_reports.report_writer import gerar_relatorio_excel
from src.io_reports.zipper import gerar_zip_arquivos

def iniciar_extracao_hibrida(caminho_excel: str, pasta_base_xmls: str, pasta_output_raiz: str):
    """
    Orquestrador master do Job Offline. Sem prints perdidos, apenas execuções silenciosas e tipadas.
    """
    # 1. Boilerplate / Setup
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_sucesso = os.path.join(pasta_output_raiz, f"Processados_{time_str}")
    sub_folder_xml = os.path.join(pasta_sucesso, "xmls")
    
    os.makedirs(sub_folder_xml, exist_ok=True)
    
    # 2. Extract Phase (Parse Excel)
    chaves_impuras = ler_coluna_b(caminho_excel)
    
    # 3. Transform Phase (Validação e Deduplicação)
    validas, invalidas = classificar_chaves(chaves_impuras)
    unicas, ejetadas_duplicadas = remover_duplicadas(validas)
    
    # 4. Search Phase (Match)
    set_alvo = frozenset(unicas)
    match_dict, xmld_duplicados = indexar_e_cruzar_xmls(pasta_base_xmls, set_alvo)
    
    # 5. Load/Copy Phase e Montagem do Relatório
    registros = []
    
    # Montando Log de Chaves Validas e Encontradas/Não Encontradas
    for chave in unicas:
        if chave in match_dict:
            src_xml = match_dict[chave]
            nome_arquivo_novo = os.path.basename(src_xml)
            dest_xml = os.path.join(sub_folder_xml, nome_arquivo_novo)
            
            # Executa Copy focado (Preserva metadados)
            shutil.copy2(src_xml, dest_xml)
            
            registros.append({
                'chave': chave,
                'status': 'encontrada',
                'observacao': 'Match efetuado e arquivo copiado.',
                'arquivo_xml': nome_arquivo_novo
            })
        else:
            registros.append({
                'chave': chave,
                'status': 'faltando',
                'observacao': 'Chave validada porém nenhum XML achado no seu Backup.',
                'arquivo_xml': ''
            })
            
    # Montando Log de Lixo
    for chave_dupla in ejetadas_duplicadas:
        registros.append({
            'chave': chave_dupla,
            'status': 'duplicada',
            'observacao': 'A chave foi injetada no planilhamento múltiplas vezes.',
            'arquivo_xml': ''
        })
        
    for chave_suja in invalidas:
         registros.append({
            'chave': chave_suja,
            'status': 'invalida',
            'observacao': 'Possível corrupção numérica ou não atende norma 44 chars.',
            'arquivo_xml': ''
        })
         
    for path_dupp in xmld_duplicados:
        registros.append({
            'chave': '',
            'status': 'xml_duplicado_no_repositorio',
            'observacao': f"Ignorado. Já havia outra via pro mesmo lote.",
            'arquivo_xml': os.path.basename(path_dupp)
        })
        
    # 6. Escrita do Log Oficial
    path_relatorio = os.path.join(pasta_sucesso, f"relatorio_final_{time_str}.xlsx")
    gerar_relatorio_excel(path_relatorio, registros)
    
    # 7. Pacote Compactado
    path_zip_alvo = os.path.join(pasta_sucesso, "xmls_encontrados")
    gerar_zip_arquivos(sub_folder_xml, path_zip_alvo) # Gerara xmls_encontrados.zip

    # Payload Final para Status Window UI (Qtd de Unicas VS Qtd Achadas Mapeadas)
    return {
        "output_dir": pasta_sucesso,
        "total_extraidas": len(chaves_impuras),
        "total_invalidas": len(invalidas),
        "total_duplicadas": len(ejetadas_duplicadas),
        "unicas_buscadas": len(unicas),
        "xmls_isolados_com_sucesso": len(match_dict.keys())
    }
