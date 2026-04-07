import unittest
from src.core.classificador_tipo import classificar_por_modelo

class TestClassificadorTipo(unittest.TestCase):
    def test_classificar_por_modelo(self):
        chaves = [
            "35230911111111111111550010000001231111111113",  # 55 = NFe
            "35230911111111111111570010000001231111111113",  # 57 = CTe
            "35230911111111111111650010000001231111111113",  # 65 = Desconhecido (NFCe)
            "invalida_curta"
        ]
        
        nfe, cte, desc = classificar_por_modelo(chaves)
        
        self.assertEqual(len(nfe), 1)
        self.assertEqual(len(cte), 1)
        self.assertEqual(len(desc), 2)
        
        self.assertTrue(nfe[0][20:22] == "55")
        self.assertTrue(cte[0][20:22] == "57")

if __name__ == '__main__':
    unittest.main()
