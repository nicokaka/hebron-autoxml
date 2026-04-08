import pytest
import re
from src.core.triagem import classificar_entrada_saida, calcular_eta, dh_evento_local
from tests.conftest import CHAVE_ENTRADA, CHAVE_SAIDA, CHAVE_FILIAL, CHAVE_CTE, CNPJ_CERT

def test_classificar_entrada_saida_nfe_entrada():
    entradas, saidas = classificar_entrada_saida([CHAVE_ENTRADA], [], CNPJ_CERT)
    assert len(entradas) == 1
    assert entradas[0] == CHAVE_ENTRADA
    assert len(saidas) == 0

def test_classificar_entrada_saida_nfe_saida_matriz():
    entradas, saidas = classificar_entrada_saida([CHAVE_SAIDA], [], CNPJ_CERT)
    assert len(entradas) == 0
    assert len(saidas) == 1
    assert saidas[0] == CHAVE_SAIDA

def test_classificar_entrada_saida_nfe_saida_filial():
    entradas, saidas = classificar_entrada_saida([CHAVE_FILIAL], [], CNPJ_CERT)
    assert len(entradas) == 0
    assert len(saidas) == 1
    assert saidas[0] == CHAVE_FILIAL

def test_classificar_entrada_saida_cte():
    entradas, saidas = classificar_entrada_saida([CHAVE_ENTRADA], [CHAVE_CTE], CNPJ_CERT)
    assert len(entradas) == 1
    assert len(saidas) == 1
    assert saidas[0] == CHAVE_CTE

def test_classificar_entrada_saida_vazio():
    entradas, saidas = classificar_entrada_saida([], [], CNPJ_CERT)
    assert entradas == []
    assert saidas == []

def test_calcular_eta_sem_saidas():
    eta = calcular_eta(total_entradas=80, total_saidas=20)
    assert eta['alerta_vermelho'] is False
    assert eta['pct_saidas'] == 20

def test_calcular_eta_com_alerta():
    eta = calcular_eta(total_entradas=0, total_saidas=100)
    assert eta['alerta_vermelho'] is True
    assert eta['pct_saidas'] == 100
    assert eta['total_horas'] == 0.4  # 100 * 15s (Playwright) / 3600 = 0.42 -> round 0.4

def test_calcular_eta_vazio():
    eta = calcular_eta(total_entradas=0, total_saidas=0)
    assert eta['alerta_vermelho'] is False
    assert eta['pct_saidas'] == 0

def test_dh_evento_local_formato():
    dh = dh_evento_local()
    # Verifica padrao de timezone (+-HH:MM) e falta de 'Z' (UTC puro nao eh permitido)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$", dh)
    assert not dh.endswith("Z")
    assert "." not in dh.split("T")[1] # Nao pode ter microsegundos
