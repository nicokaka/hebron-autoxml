def classificar_por_modelo(chaves_unicas: list) -> tuple[list, list, list]:
    """
    Classifica a chave de acesso 44 dígitos no respectivo tipo de documento
    com base na posição de modelo (posição 21-22).
    
    55: NF-e (Nota Fiscal Eletrônica)
    57: CT-e (Conhecimento de Transporte)
    
    Retorna: (chaves_nfe, chaves_cte, chaves_desconhecidas)
    """
    chaves_nfe = []
    chaves_cte = []
    chaves_desconhecidas = []
    
    for chave in chaves_unicas:
        if len(chave) != 44 or not chave.isdigit():
            # Falha de sanidade se por acaso passar pelo validador sem higiene total
            chaves_desconhecidas.append(chave)
            continue
            
        modelo = chave[20:22]
        if modelo == "55":
            chaves_nfe.append(chave)
        elif modelo == "57":
            chaves_cte.append(chave)
        else:
            chaves_desconhecidas.append(chave)
            
    return chaves_nfe, chaves_cte, chaves_desconhecidas
