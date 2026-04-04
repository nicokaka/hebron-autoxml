"""
Testes obrigatórios estritos da Etapa 0.2.
Valida localmente o fluxo interno de extração XML e descompressão, provando
que as funções críticas sobrevivem ao Payload Sefaz antes mesmo ir pra Web e queimar limite mTLS.
"""

import sys
import os
import unittest
import base64
import zlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../prova_tecnica')))
import helpers

class TestSefazParsing(unittest.TestCase):
    def test_descompressao_zlib(self):
        # Emula um dummy XML
        xml_original = '<?xml version="1.0"?><nfeProc><NFe>DummyData</NFe></nfeProc>'
        # GZIP padrao win/linux para XMLs web usa wbits 31
        compressor = zlib.compressobj(wbits=31)
        zipado_bytes = compressor.compress(xml_original.encode('utf-8')) + compressor.flush()
        codigo_b64 = base64.b64encode(zipado_bytes).decode('utf-8')
        
        resultado = helpers.descompactar_base64_zip(codigo_b64)
        self.assertEqual(xml_original, resultado)
        
    def test_parse_retorno_vazio(self):
        payload = """<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><nfeDistDFeInteresseResponse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe"><nfeDistDFeInteresseResult><retDistDFeInt versao="1.38" xmlns="http://www.portalfiscal.inf.br/nfe"><tpAmb>2</tpAmb><verAplic>SVRS2022</verAplic><cStat>137</cStat><xMotivo>Nenhum documento localizado para o Destinatario</xMotivo><dhResp>2023-01-01T00:00:00-03:00</dhResp><ultNSU>000000000000001</ultNSU><maxNSU>000000000000001</maxNSU></retDistDFeInt></nfeDistDFeInteresseResult></nfeDistDFeInteresseResponse></soap:Body></soap:Envelope>"""
        
        parsed = helpers.parse_retorno_distribuicao(payload, is_cte=False)
        self.assertEqual(parsed['cStat'], '137')
        self.assertEqual(parsed['xMotivo'], 'Nenhum documento localizado para o Destinatario')
        self.assertEqual(len(parsed['docs']), 0)
        self.assertEqual(parsed['ultNSU'], '000000000000001')

    def test_parse_retorno_com_documento(self):
        payload = """<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><nfeDistDFeInteresseResponse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe"><nfeDistDFeInteresseResult><retDistDFeInt versao="1.38" xmlns="http://www.portalfiscal.inf.br/nfe"><tpAmb>2</tpAmb><verAplic>SVRS</verAplic><cStat>138</cStat><xMotivo>Documento localizado</xMotivo><dhResp>2023-01-01T12:00:00-03:00</dhResp><ultNSU>000000000000002</ultNSU><maxNSU>000000000000005</maxNSU><loteDistDFeInt><docZip NSU="000000000000002" schema="resNFe_v1.01.xsd">SGVicm9uQXV0b1hNTFRlc3Rl</docZip></loteDistDFeInt></retDistDFeInt></nfeDistDFeInteresseResult></nfeDistDFeInteresseResponse></soap:Body></soap:Envelope>"""
        
        parsed = helpers.parse_retorno_distribuicao(payload, is_cte=False)
        self.assertEqual(parsed['cStat'], '138')
        self.assertEqual(len(parsed['docs']), 1)
        self.assertEqual(parsed['docs'][0]['NSU'], '000000000000002')
        self.assertEqual(parsed['docs'][0]['schema'], 'resNFe_v1.01.xsd')
        self.assertTrue('SGVicm' in parsed['docs'][0]['content_b64'])

    def test_parse_soap_fault(self):
        payload = """<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><soap:Fault><soap:Code><soap:Value>soap:Sender</soap:Value></soap:Code><soap:Reason><soap:Text xml:lang="en">Schema Inválido</soap:Text></soap:Reason></soap:Fault></soap:Body></soap:Envelope>"""
        parsed = helpers.parse_retorno_distribuicao(payload, is_cte=True)
        self.assertTrue('error' in parsed)
        self.assertTrue('Schema Inválido' in parsed['error'])

if __name__ == '__main__':
    unittest.main()
