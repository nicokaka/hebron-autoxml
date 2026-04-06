import unittest
from src.core.parser_excel import ler_coluna_b
import openpyxl
import os

class TestParserExcel(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_parser.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["ID", "CHAVE", "VALOR"])
        ws.append([1, "35230000000000000000000000000000000000000111", 100])
        ws.append([2, None, 200]) # Vazio
        ws.append([3, "  35230000000000000000000000000000000000000222  ", 300]) # Com espacos
        wb.save(self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_ler_coluna_b_ignora_cabecalho_e_vazios(self):
        chaves = ler_coluna_b(self.test_file)
        self.assertEqual(len(chaves), 2)
        self.assertEqual(chaves[0], "35230000000000000000000000000000000000000111")
        self.assertEqual(chaves[1], "35230000000000000000000000000000000000000222")

    def test_ler_coluna_b_converte_numeros_excel_corretamente(self):
        """
        Excel pode armazenar chaves de 44 dígitos como número (int ou float).
        str(float) geraria notação científica (3.523e+43), destruindo a chave.
        O parser deve converter para int primeiro.
        """
        test_file_num = "test_parser_numeric.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["ID", "CHAVE"])
        # Simula célula numérica (como Excel pode interpretar um número grande)
        ws.append([1, 35230000000000000000000000000000000000000111])
        # Simula célula que já é float
        ws.append([2, float(35230000000000000000000000000000000000000222)])
        wb.save(test_file_num)

        try:
            chaves = ler_coluna_b(test_file_num)
            self.assertEqual(len(chaves), 2)
            # Ambas devem ser strings de 44 dígitos, sem notação científica
            for chave in chaves:
                self.assertEqual(len(chave), 44, f"Chave truncada: {chave}")
                self.assertTrue(chave.isdigit(), f"Chave não numérica: {chave}")
        finally:
            if os.path.exists(test_file_num):
                os.remove(test_file_num)

if __name__ == '__main__':
    unittest.main()
