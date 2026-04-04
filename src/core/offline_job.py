import os
import shutil
from datetime import datetime

from src.core.parser_excel import ler_coluna_b
from src.core.key_validator import classificar_chaves
from src.core.deduplicador import remover_duplicadas
from src.core.matcher_xml import indexar_e_cruzar_xmls
from src.io_reports.report_writer import gerar_relatorio_excel
from src.io_reports.zipper import gerar_zip_arquivos

def iniciar_extracao_hibrida(caminho_excel: str, pasta_base_xmls: str, pasta_output_raiz: str) -> dict:
    """Orquestra o fluxo offline de validação e cruzamento de XMLs."""
    
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_sucesso = os.path.join(pasta_output_raiz, f"Processados_{time_str}")
    sub_pasta_xml = os.path.join(pasta_sucesso, "xmls")
    
    os.makedirs(sub_pasta_xml, exist_ok=True)
    
    chaves_impuras = ler_coluna_b(caminho_excel)
    
    chaves_validas, chaves_invalidas = classificar_chaves(chaves_impuras)
    chaves_unicas, chaves_duplicadas = remover_duplicadas(chaves_validas)
    
    set_alvo = frozenset(chaves_unicas)
    dicionario_match, xmls_duplicados = indexar_e_cruzar_xmls(pasta_base_xmls, set_alvo)
    
    registros_relatorio = []
    
    for chave in chaves_unicas:
        if chave in dicionario_match:
            caminho_origem_xml = dicionario_match[chave]
            nome_arquivo = os.path.basename(caminho_origem_xml)
            caminho_destino_xml = os.path.join(sub_pasta_xml, nome_arquivo)
            
            shutil.copy2(caminho_origem_xml, caminho_destino_xml)
            
            registros_relatorio.append({
                'chave': chave,
                'status': 'encontrada',
                'observacao': 'Arquivo localizado e copiado.',
                'arquivo_xml': nome_arquivo
            })
        else:
            registros_relatorio.append({
                'chave': chave,
                'status': 'faltando',
                'observacao': 'XML não encontrado no diretório base.',
                'arquivo_xml': ''
            })
            
    for chave in chaves_duplicadas:
        registros_relatorio.append({
            'chave': chave,
            'status': 'duplicada',
            'observacao': 'Chave informada múltiplas vezes no Excel.',
            'arquivo_xml': ''
        })
        
    for chave in chaves_invalidas:
         registros_relatorio.append({
            'chave': chave,
            'status': 'invalida',
            'observacao': 'Formato incorreto (esperado 44 dígitos).',
            'arquivo_xml': ''
        })
         
    for caminho_duplicado in xmls_duplicados:
        registros_relatorio.append({
            'chave': '',
            'status': 'xml_duplicado_no_repositorio',
            'observacao': 'XML descartado pois outro arquivo com a mesma chave já foi processado.',
            'arquivo_xml': os.path.basename(caminho_duplicado)
        })
        
    # Relatório com nome fixo, pois a pasta pai já possui o timestamp
    caminho_relatorio = os.path.join(pasta_sucesso, "relatorio_final.xlsx")
    gerar_relatorio_excel(caminho_relatorio, registros_relatorio)
    
    caminho_zip = os.path.join(pasta_sucesso, "xmls_encontrados")
    gerar_zip_arquivos(sub_pasta_xml, caminho_zip)

    return {
        "diretorio_saida": pasta_sucesso,
        "total_lidas": len(chaves_impuras),
        "total_invalidas": len(chaves_invalidas),
        "total_duplicadas": len(chaves_duplicadas),
        "total_unicas": len(chaves_unicas),
        "total_encontradas": len(dicionario_match)
    }
