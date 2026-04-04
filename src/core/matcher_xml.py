import os
import re

def parse_chave_em_xml(path_arquivo: str) -> str:
    """Extrai chave de 44 dígitos de tags Id (NFe/CTe) no XML."""
    regex_chave = re.compile(r'(?:NFe|CTe)(\d{44})')
    try:
        with open(path_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            for i, linha in enumerate(f):
                if i > 150:
                    break
                match = regex_chave.search(linha)
                if match:
                    return match.group(1)
        return ""
    except Exception:
        return ""

def indexar_e_cruzar_xmls(diretorio_base: str, chaves_alvo: frozenset) -> tuple[dict, list]:
    """
    Varre os XMLs de um diretório.
    Busca match no nome do arquivo primeiro. Se não achar, busca no conteúdo.
    Retorna (dict_matchs, lista_duplicados).
    """
    match_index = {}
    duplicados_repositorio = []
    
    # Regex para pegar exatos 44 dígitos isolados no nome do arquivo
    regex_44 = re.compile(r'(?<!\d)(\d{44})(?!\d)')
    
    for root, dirs, files in os.walk(diretorio_base):
        for file in files:
            if file.lower().endswith('.xml'):
                caminho_completo = os.path.join(root, file)
                
                chave_detectada = ""
                busca_nome = regex_44.search(file)
                if busca_nome:
                    chave_detectada = busca_nome.group(1)
                
                # Fallback: tentar conteúdo se a chave do nome for vazia ou não for alvo
                if not chave_detectada or chave_detectada not in chaves_alvo:
                    chave_detectada_interna = parse_chave_em_xml(caminho_completo)
                    if chave_detectada_interna:
                        chave_detectada = chave_detectada_interna
                
                if chave_detectada and chave_detectada in chaves_alvo:
                    if chave_detectada in match_index:
                        duplicados_repositorio.append(caminho_completo)
                    else:
                        match_index[chave_detectada] = caminho_completo
                        
    return match_index, duplicados_repositorio
