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

if __name__ == '__main__':
    unittest.main()
