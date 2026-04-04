import openpyxl

def gerar_relatorio_excel(caminho_saida: str, records: list[dict]):
    """
    Constrói a planilha limpa contendo o log do faturamento.
    records: list de dicionários com as chaves:
        - 'chave'
        - 'status'
        - 'observacao'
        - 'arquivo_xml'
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Relatório Integração Offline"
    
    # Cabeçalho
    cabecalhos = ["CHAVE_NF_CT", "STATUS", "OBSERVAÇÃO", "CAMINHO_DO_ARQUIVO"]
    ws.append(cabecalhos)
    
    for r in records:
        ws.append([
            r.get('chave', ''),
            r.get('status', 'DESCONHECIDO'),
            r.get('observacao', ''),
            r.get('arquivo_xml', '')
        ])
        
    wb.save(caminho_saida)
    wb.close()
