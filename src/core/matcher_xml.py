import os
import re

def parse_chave_em_xml(path_arquivo: str) -> str:
    """Extrai chave de 44 dígitos através de variação de Tags Id do XML de forma robusta e levíssima."""
    regex_chave = re.compile(r'(NFe|CTe)(\d{44})')
    try:
        # Lê apenas as primeiras linhas (onde normalmente está o env/Id) pra não sobrecarregar memória
        with open(path_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            for i, linha in enumerate(f):
                if i > 50:  # Evita ler the whole file se for imenso
                    break
                match = regex_chave.search(linha)
                if match:
                    return match.group(2)
        return ""
    except Exception:
        return ""

def indexar_e_cruzar_xmls(diretorio_base: str, chaves_alvo: frozenset) -> tuple[dict, list]:
    """
    Varre os XMLs de um diretório recursivamente.
    Busca match primeiro no Nome do Arquivo, e via Fallback abre o arquivo procurando a Tag.
    Retorna:
      - dict do tipo { '44digitos': 'caminho_absoluto' } com todos os matchs encontrados.
      - list de paths xml que foram achados duplicados para a mesma chave.
    """
    match_index = {}
    duplicados_no_repositorio = []
    
    regex_44 = re.compile(r'\d{44}')
    
    for root, dirs, files in os.walk(diretorio_base):
        for file in files:
            if file.lower().endswith('.xml'):
                caminho_completo = os.path.join(root, file)
                
                chave_detectada = ""
                # Tenta Match por Nome do Arquivo Primeiro (Mais rápido, I/O Free)
                busca_nome = regex_44.search(file)
                if busca_nome:
                    chave_detectada = busca_nome.group()
                
                # Se o nome não tiver 44 digitos clarividentes, abre o arquivo
                if not chave_detectada or chave_detectada not in chaves_alvo:
                     chave_detectada_interna = parse_chave_em_xml(caminho_completo)
                     if chave_detectada_interna:
                         chave_detectada = chave_detectada_interna
                
                if chave_detectada and chave_detectada in chaves_alvo:
                    if chave_detectada in match_index:
                        # Colisão: Mais de um XML achado atrelado a mesma chave.
                        duplicados_no_repositorio.append(caminho_completo)
                    else:
                        match_index[chave_detectada] = caminho_completo
                        
    return match_index, duplicados_no_repositorio
