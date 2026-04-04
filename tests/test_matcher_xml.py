import unittest
import os
import shutil
from src.core.matcher_xml import indexar_e_cruzar_xmls

class TestMatcherXML(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_xmls_matcher"
        os.makedirs(self.test_dir, exist_ok=True)
        
        # XML match nome
        with open(os.path.join(self.test_dir, "35230000000000000000000000000000000000000111-nfe.xml"), "w") as f:
            f.write("<xml></xml>")
            
        # XML match conteudo
        with open(os.path.join(self.test_dir, "nota_esquisita.xml"), "w") as f:
            f.write('<nfeProc> <NFe123> <infNFe Id="NFe35230000000000000000000000000000000000000222"></infNFe> </nfeProc>')
            
        # XML ruido nome parecendo chave mas nao eh alvo
        with open(os.path.join(self.test_dir, "99999000000000000000000000000000000000000999-nfe.xml"), "w") as f:
            f.write("<xml></xml>")
            
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_indexar_e_cruzar_xmls(self):
        alvos = frozenset([
            "35230000000000000000000000000000000000000111",
            "35230000000000000000000000000000000000000222",
            "35230000000000000000000000000000000000000000" # Faltante
        ])
        
        match_dict, duplicados = indexar_e_cruzar_xmls(self.test_dir, alvos)
        
        self.assertEqual(len(match_dict), 2)
        self.assertIn("35230000000000000000000000000000000000000111", match_dict)
        self.assertIn("35230000000000000000000000000000000000000222", match_dict)
        self.assertEqual(len(duplicados), 0)

if __name__ == '__main__':
    unittest.main()
