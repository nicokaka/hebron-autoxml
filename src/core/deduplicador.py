def remover_duplicadas(chaves_validas: list[str]) -> tuple[list[str], list[str]]:
    """
    Remove duplicadas e mantém a ordem original da primeira aparição.
    Retorna (chaves_unicas, chaves_duplicadas_ejetadas).
    """
    vistas = set()
    unicas = []
    ejetadas = []
    
    for ch in chaves_validas:
        if ch not in vistas:
            vistas.add(ch)
            unicas.append(ch)
        else:
            ejetadas.append(ch)
            
    return unicas, ejetadas
