import unittest
from src.core.deduplicador import remover_duplicadas

class TestDeduplicador(unittest.TestCase):
    def test_remover_duplicadas(self):
        entrada = ["A", "B", "A", "C", "B", "D"]
        unicas, duplicadas = remover_duplicadas(entrada)
        
        self.assertEqual(unicas, ["A", "B", "C", "D"])
        self.assertEqual(duplicadas, ["A", "B"])

if __name__ == '__main__':
    unittest.main()
