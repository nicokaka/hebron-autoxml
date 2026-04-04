import openpyxl

def ler_coluna_b(caminho_arquivo: str) -> list[str]:
    """
    Lê a coluna B de um arquivo Excel e retorna uma lista com os itens puros em string.
    Lida com células vazias de forma silenciosa e abstrai o cabeçalho se houver.
    """
    wb = openpyxl.load_workbook(caminho_arquivo, read_only=True, data_only=True)
    planilha = wb.active
    
    chaves = []
    
    # Itera iterativamente na Coluna B
    for row in planilha.iter_rows(min_col=2, max_col=2, values_only=True):
        valor = row[0]
        if valor is not None:
            valor_str = str(valor).strip()
            # Ignora cabeçalhos genéricos
            if valor_str and valor_str.lower() not in ["chave", "chave de acesso", "cod_chave_acesso_nfel", "chaves"]:
                chaves.append(valor_str)
                
    wb.close()
    return chaves
