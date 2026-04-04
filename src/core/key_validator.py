def validar_chave(chave: str) -> tuple[bool, str]:
    """
    Validação base para chaves NF-e ou CT-e:
    Obrigatórios exatos 44 numerais.
    Retorna (is_valid, chave_original).
    """
    chave_limpa = chave.strip()
    if len(chave_limpa) == 44 and chave_limpa.isdigit():
        return True, chave_limpa
    
    return False, chave_limpa

def classificar_chaves(lista_chaves: list[str]) -> tuple[list[str], list[str]]:
    """
    Peneira a lista bruta dividindo-a em chaves aceitas ICP e sujas.
    """
    validas = []
    invalidas = []
    
    for c in lista_chaves:
        valida, ch = validar_chave(c)
        if valida:
            validas.append(ch)
        else:
            invalidas.append(ch)
            
    return validas, invalidas
