import unittest
import os
import shutil
import openpyxl

from src.core.offline_job import iniciar_extracao_hibrida

class TestOfflineJob(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_offline_job_temp"
        os.makedirs(self.test_dir, exist_ok=True)
        
        self.excel_path = os.path.join(self.test_dir, "base_contabilidade.xlsx")
        self.xml_repo = os.path.join(self.test_dir, "falsa_nuvem")
        self.output_raiz = os.path.join(self.test_dir, "outputs")
        
        os.makedirs(self.xml_repo, exist_ok=True)
        os.makedirs(self.output_raiz, exist_ok=True)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["ID", "CHAVE", "VALOR"])
        ws.append(["1", "35230000000000000000000000000000000000000111", "R$ 100.00"]) # Valida
        ws.append(["2", "35230000000000000000000000000000000000000222", "R$ 200.00"]) # Valida
        ws.append(["2", "35230000000000000000000000000000000000000222", "R$ 200.00"]) # Duplicata
        ws.append(["3", "LIXO123", "R$ 0"]) # Invalida
        wb.save(self.excel_path)
        
        with open(os.path.join(self.xml_repo, "nota_fiscal_35230000000000000000000000000000000000000111-nfe.xml"), 'w') as f:
            f.write("<nfeProc><chNFe>FALSO_AQUI</chNFe></nfeProc>")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_iniciar_extracao_hibrida(self):
        resultado = iniciar_extracao_hibrida(self.excel_path, self.xml_repo, self.output_raiz)
        
        self.assertEqual(resultado['total_lidas'], 4)
        self.assertEqual(resultado['total_invalidas'], 1) 
        self.assertEqual(resultado['total_duplicadas'], 1)
        self.assertEqual(resultado['total_unicas'], 2)
        self.assertEqual(resultado['total_encontradas'], 1)
        
        path_output_dinamico = resultado['diretorio_saida']
        
        zip_path = os.path.join(path_output_dinamico, "xmls_encontrados.zip")
        self.assertTrue(os.path.isfile(zip_path))
        
        excel_log = os.path.join(path_output_dinamico, "relatorio_final.xlsx")
        self.assertTrue(os.path.isfile(excel_log))

if __name__ == '__main__':
    unittest.main()
