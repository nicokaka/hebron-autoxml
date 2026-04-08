import pytest
from lxml import etree
import os
from unittest.mock import patch, Mock
from src.core.sefaz_manifestacao import _gerar_xml_evento, _assinar_evento, _montar_envelope, _parsear_resposta, enviar_manifestacao
from tests.conftest import CHAVE_ENTRADA

def test_gerar_xml_evento():
    xml = _gerar_xml_evento("08939548000103", CHAVE_ENTRADA, "2")
    assert 'xmlns="http://www.portalfiscal.inf.br/nfe"' in xml
    assert f'Id="ID210210{CHAVE_ENTRADA}01"' in xml
    assert '<cOrgao>91</cOrgao>' in xml
    assert '<tpEvento>210210</tpEvento>' in xml
    assert '<descEvento>Ciencia da Operacao</descEvento>' in xml

def test_assinar_evento(cert_fake_pem):
    cert_pem, key_pem = cert_fake_pem
    xml_bruto = _gerar_xml_evento("08939548000103", CHAVE_ENTRADA, "2")
    
    xml_assinado = _assinar_evento(xml_bruto, cert_pem, key_pem)
    
    # Validar se a assinatura foi aplicada
    assert "Signature" in xml_assinado
    assert 'Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"' in xml_assinado
    assert 'Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"' in xml_assinado
    assert 'Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"' in xml_assinado
    
    # Macete xml:id nao pode vazar pro xml final
    assert "xml:id" not in xml_assinado

def test_montar_envelope():
    envelope = _montar_envelope(["<evento>1</evento>", "<evento>2</evento>"], id_lote=1, tp_amb="1")
    assert '<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">' in envelope
    assert '<nfeDadosMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeRecepcaoEvento4">' in envelope
    assert '<idLote>1</idLote>' in envelope
    assert '<evento>1</evento><evento>2</evento>' in envelope

def test_parsear_resposta():
    resp_mock = f"""
    <retEnvEvento xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">
        <retEvento versao="1.00">
            <infEvento>
                <chNFe>{CHAVE_ENTRADA}</chNFe>
                <cStat>135</cStat>
            </infEvento>
        </retEvento>
        <retEvento versao="1.00">
            <infEvento>
                <chNFe>OUTRACHAVE</chNFe>
                <cStat>573</cStat>
            </infEvento>
        </retEvento>
    </retEnvEvento>
    """
    env_cstat, env_xmotivo, res = _parsear_resposta(resp_mock)
    assert res.get(CHAVE_ENTRADA) == "135"
    assert res.get("OUTRACHAVE") == "573"

def test_parsear_resposta_lixo():
    _, _, res1 = _parsear_resposta("<html><body>Error</body></html>")
    assert res1 == {}
    _, _, res2 = _parsear_resposta("")
    assert res2 == {}

@patch("src.core.sefaz_manifestacao.requests.post")
def test_enviar_manifestacao(mock_post, mock_temp_dir, cert_fake_pem):
    # Setup de certs
    cert_path = os.path.join(mock_temp_dir, "cert.pem")
    key_path = os.path.join(mock_temp_dir, "key.pem")
    with open(cert_path, "wb") as f: f.write(cert_fake_pem[0])
    with open(key_path, "wb") as f: f.write(cert_fake_pem[1])

    # Setup do mock post
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.text = f"""
    <retEnvEvento xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">
        <cStat>128</cStat>
        <xMotivo>Lote de Evento Processado</xMotivo>
        <retEvento versao="1.00"><infEvento><chNFe>{CHAVE_ENTRADA}</chNFe><cStat>135</cStat></infEvento></retEvento>
    </retEnvEvento>
    """
    mock_post.return_value = mock_resp

    chaves = [CHAVE_ENTRADA] * 25 # 25 chaves devia dividir em 2 lotes (20, 5)
    
    logs = []
    resultado = enviar_manifestacao(
        cert_path, key_path, "08939548000103", chaves, "homologacao", on_progresso=lambda m: logs.append(m)
    )
    
    # Conferir se dividiu em lotes corretamente
    assert mock_post.call_count == 2
    
    # O mock text sempre diz que a chave entrada deu 135. Como temos 25 duplicadas na lista de entrada, 
    # o dict_lote tem só 1 entrada no parse_resposta
    assert resultado.get(CHAVE_ENTRADA) == "135"
    assert any("Lote 1: 1/20" in l for l in logs)
    assert any("Lote 2: 1/5" in l for l in logs)
