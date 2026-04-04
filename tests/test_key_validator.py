import unittest
from src.core.key_validator import validar_chave, classificar_chaves

class TestKeyValidator(unittest.TestCase):
    def test_validar_chave(self):
        # Valida
        valido, chave = validar_chave("35230000000000000000000000000000000000000111")
        self.assertTrue(valido)
        
        # Invalida - letras
        valido, _ = validar_chave("A5230000000000000000000000000000000000000111")
        self.assertFalse(valido)
        
        # Invalida - curto
        valido, _ = validar_chave("123")
        self.assertFalse(valido)

    def test_classificar_chaves(self):
        entrada = [
            "35230000000000000000000000000000000000000111",
            "LIXO123",
            "35230000000000000000000000000000000000000222"
        ]
        validas, invalidas = classificar_chaves(entrada)
        self.assertEqual(len(validas), 2)
        self.assertEqual(len(invalidas), 1)
        self.assertEqual(invalidas[0], "LIXO123")

if __name__ == '__main__':
    unittest.main()
