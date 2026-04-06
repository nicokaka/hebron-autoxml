import openpyxl

def ler_coluna_b(caminho_arquivo: str) -> list[str]:
    """
    Lê a coluna B de um arquivo Excel, ignorando a primeira linha (cabeçalho).
    Retorna uma lista de strings.
    """
    wb = openpyxl.load_workbook(caminho_arquivo, data_only=True)
    try:
        planilha = wb.active
        
        chaves = []
        
        for row in planilha.iter_rows(min_row=2, min_col=2, max_col=2, values_only=True):
            valor = row[0]
            if valor is not None:
                # Excel pode armazenar chaves numéricas como int ou float.
                # str(float) gera notação científica (ex: 3.523e+43), destruindo a chave.
                # Converter para int primeiro preserva todos os dígitos.
                if isinstance(valor, float):
                    valor = int(valor)
                valor_str = str(valor).strip()
                if valor_str:
                    chaves.append(valor_str)
    finally:
        wb.close()
    return chaves
