import unittest
import os
import shutil
import openpyxl

from src.core.offline_job import iniciar_extracao_hibrida

class TestCoreOffline(unittest.TestCase):
    def setUp(self):
        # Base Path
        self.test_dir = os.path.join(os.path.dirname(__file__), "temp_offline_mock")
        os.makedirs(self.test_dir, exist_ok=True)
        
        self.excel_path = os.path.join(self.test_dir, "base_contabilidade.xlsx")
        self.xml_repo = os.path.join(self.test_dir, "falsa_nuvem")
        self.output_raiz = os.path.join(self.test_dir, "outputs")
        
        os.makedirs(self.xml_repo, exist_ok=True)
        os.makedirs(self.output_raiz, exist_ok=True)
        
        # 1. Mocking Excel Report (Planilha)
        wb = openpyxl.Workbook()
        ws = wb.active
        # Header Lixo e Coluna A random
        ws.append(["ID", "COD_CHAVE_ACESSO_NFEL", "VALOR"])
        ws.append(["1", "35230000000000000000000000000000000000000111", "R$ 100.00"]) # Valida Lida Local
        ws.append(["2", "35230000000000000000000000000000000000000222", "R$ 200.00"]) # Valida Ausente
        ws.append(["2", "35230000000000000000000000000000000000000222", "R$ 200.00"]) # Duplicata
        ws.append(["3", "LIXO123", "R$ 0"]) # Invalida
        ws.append(["4", None, "R$ 0"]) # Linhas Vazias
        ws.append(["5", "35230000000000000000000000000000000000000333", "R$ 10.00"]) # Valida pelo XML Interno
        wb.save(self.excel_path)
        
        # 2. Mocking XML Files (Nuvem Falsa Local)
        # Match direto pelo NOME DO ARQUIVO
        with open(os.path.join(self.xml_repo, "nota_fiscal_35230000000000000000000000000000000000000111-nfe.xml"), 'w') as f:
            f.write("<nfeProc><chNFe>FALSO_AQUI</chNFe></nfeProc>")
            
        # Match Pelo Conteúdo Interno (Nome feio, mas Tag válida CTe)
        with open(os.path.join(self.xml_repo, "comprovante_estranho.xml"), 'w') as f:
             # Match by regex NFe<Chave> ou CTe...
             f.write('<?xml versao="1.0"?><teste><infNFe Id="NFe35230000000000000000000000000000000000000333"></infNFe></teste>')
             
        # XML duplicado gerando colisão passiva (Sendo tolerado sem quebrar)
        with open(os.path.join(self.xml_repo, "nota_fiscal_35230000000000000000000000000000000000000111-copia.xml"), 'w') as f:
             f.write("")

    def tearDown(self):
        # Limpa o Lixo Pós-Teste (Apenas se não quisermos auditar a pasta isolada. Deixarei para depuração passiva)
        shutil.rmtree(self.test_dir, ignore_errors=True)
        pass
        
    def test_pipeline_extracao_off_line_completo(self):
        # Roda o Maestro Master
        resultado = iniciar_extracao_hibrida(self.excel_path, self.xml_repo, self.output_raiz)
        
        # Analytics Asserts
        self.assertEqual(resultado['total_extraidas'], 5)
        self.assertEqual(resultado['total_duplicadas'], 1)   # O 222 se repetiu
        self.assertEqual(resultado['total_invalidas'], 1)    # O LIXO123
        self.assertEqual(resultado['unicas_buscadas'], 3)    # 111, 222, 333
        self.assertEqual(resultado['xmls_isolados_com_sucesso'], 2) # O 222 é o 'Ausente' no FolderFalso
        
        # Validation FS
        path_output_dinamico = resultado['output_dir']
        
        # Checar se ZIP apareceu e se Planilha Output apareceu
        zip_path = os.path.join(path_output_dinamico, "xmls_encontrados.zip")
        self.assertTrue(os.path.isfile(zip_path), "ZIP não foi compilado no Job Offline.")
        
        excel_log = [f for f in os.listdir(path_output_dinamico) if f.endswith('.xlsx')]
        self.assertEqual(len(excel_log), 1, "Planilha de Log Oficial não concebida!")

if __name__ == '__main__':
    unittest.main()
