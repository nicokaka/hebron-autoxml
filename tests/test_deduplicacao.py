import os
import unittest

from src.core.key_validator import classificar_chaves
from src.core.deduplicador import remover_duplicadas

def parse_e_deduplicar_chaves(filepath: str):
    """
    Lê o arquivo de chaves textuais da fixture pre-gerada,
    integra a lógica do core para validação e remoção.
    Retorna a contagem exata (total_bruto, chaves_unicas_limpas, invalidas).
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Fixture não encontrada no disco: {filepath}")
        
    with open(filepath, 'r', encoding='utf-8') as iterador:
        linhas = [str(linha.strip()) for linha in iterador if linha.strip()]
        
    validas, invalidas = classificar_chaves(linhas)
    unicas, duplicadas = remover_duplicadas(validas)
    
    return len(linhas), unicas, invalidas

class TestDeduplicacaoProcessamentoBatch(unittest.TestCase):
    def setUp(self):
        # Aponta estritamente para o root_dir/tests/fixture_chaves.txt
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        self.fixture_path = os.path.join(diretorio_atual, 'fixture_chaves.txt')

    def test_valida_fluxo_excel_mock_coluna_b(self):
        total_lidas, array_unicas, array_invalidas = parse_e_deduplicar_chaves(self.fixture_path)
        
        # A matemática oficial declarada no input foi 122, mas a massa literal copiada foi 120.
        self.assertEqual(
            total_lidas, 
            120, 
            f"FALHA [Leitura bruta]: O parser consumiu {total_lidas} registros, devendo ser 120 da fixture real."
        )
        
        self.assertEqual(
            len(array_invalidas), 
            0, 
            f"FALHA [Formatação Suja]: Chaves fora do padrao: {array_invalidas}"
        )
        
        self.assertEqual(
            len(array_unicas), 
            76, 
            f"FALHA [Deduplicador Unique]: Sobraram {len(array_unicas)} em vez de 76."
        )
        
        # Check Final Matemático
        qtd_duplicadas_descartadas = total_lidas - len(array_unicas)
        self.assertEqual(
            qtd_duplicadas_descartadas, 
            44, 
            f"FALHA [Matemática Descarte]: O gap foi {qtd_duplicadas_descartadas}, esperado era 44."
        )
        
        print("\n\n---------------- LOG DO TESTE DEDUPLICADOR (B-COLUMN) ----------------")
        print(f" [OK] Carga bruta de dados local: {total_lidas} linhas literais encontradas.")
        print(f" [OK] Carga de chaves impuras/sujas: {len(array_invalidas)} registros excluídos.")
        print(f" [OK] Conjunto Único: Extração de exatas {len(array_unicas)} chaves primárias distintas.")
        print(f" [OK] Deduplicação concluida: {qtd_duplicadas_descartadas} duplicações ejetadas da fila.")
        print("----------------------------------------------------------------------\n")

if __name__ == '__main__':
    unittest.main()
