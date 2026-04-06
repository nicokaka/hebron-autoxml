import openpyxl

def gerar_relatorio_excel(caminho_saida: str, registros: list[dict]):
    """Gera relatório .xlsx formatado a partir dos registros de processamento."""
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        ws.title = "Relatório Integração"
        
        cabecalhos = ["CHAVE_NF_CT", "STATUS", "OBSERVAÇÃO", "CAMINHO_DO_ARQUIVO"]
        ws.append(cabecalhos)
        
        # Formatação básica de colunas
        ws.column_dimensions['A'].width = 50
        ws.column_dimensions['B'].width = 25
        ws.column_dimensions['C'].width = 50
        ws.column_dimensions['D'].width = 60
        
        for r in registros:
            ws.append([
                r.get('chave', ''),
                r.get('status', 'DESCONHECIDO'),
                r.get('observacao', ''),
                r.get('arquivo_xml', '')
            ])
            
        wb.save(caminho_saida)
    finally:
        wb.close()
