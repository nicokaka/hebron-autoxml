import requests
from requests.exceptions import RequestException

from src.core.sefaz_tools import descompactar_base64_zip, parse_retorno_distribuicao

def _payload_cte_chave(uf_autor: str, cnpj: str, chave: str, ambiente: str) -> str:
    tp_amb = "2" if ambiente.lower() == "homologacao" else "1"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <cteDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/cte/wsdl/CTeDistribuicaoDFe">
      <cteDadosMsg>
        <distDFeInt xmlns="http://www.portalfiscal.inf.br/cte" versao="1.00">
          <tpAmb>{tp_amb}</tpAmb>
          <cUFAutor>{uf_autor}</cUFAutor>
          <CNPJ>{cnpj}</CNPJ>
          <consChCTe>
            <chCTe>{chave}</chCTe>
          </consChCTe>
        </distDFeInt>
      </cteDadosMsg>
    </cteDistDFeInteresse>
  </soap12:Body>
</soap12:Envelope>"""

def consultar_cte_chave(cert_path: str, key_path: str, uf_autor: str, cnpj: str, chave: str, ambiente: str) -> dict:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    if ambiente.lower() == "homologacao":
        url = "https://hom1.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx"
    else:
        url = "https://www1.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx"
        
    headers = {
        'Content-Type': 'application/soap+xml; charset=utf-8',
        'SOAPAction': 'http://www.portalfiscal.inf.br/cte/wsdl/CTeDistribuicaoDFe/cteDistDFeInteresse'
    }
    
    payload = _payload_cte_chave(uf_autor, cnpj, chave, ambiente)
    
    try:
        resp = requests.post(url, data=payload, headers=headers, cert=(cert_path, key_path), verify=False, timeout=25)
        resp_text = resp.text
    except RequestException as e:
        return {'status': 'erro_rede', 'mensagem': f"Time-Out ou bloqueio TLS: {str(e)}"}
        
    dados_parsed = parse_retorno_distribuicao(resp_text, is_cte=True)
    
    if 'error' in dados_parsed:
        return {'status': 'erro_soap', 'mensagem': dados_parsed['error']}
        
    cStat = dados_parsed.get('cStat')
    xMotivo = dados_parsed.get('xMotivo', 'Erro na Sefaz')
    
    if cStat is None:
        return {'status': 'erro_soap', 'mensagem': "O servidor não retornou a tag cStat esperada no XML."}
    
    if cStat in ("137", "236"):
        return {'status': 'nao_encontrada', 'mensagem': f"Documento não localizado no ambiente Nacional (cStat {cStat})."}
        
    if not dados_parsed['docs']:
        return {'status': 'rejeitado', 'mensagem': f"cStat {cStat} retornado sem documentos: {xMotivo}"}
        
    xml_conteudo = None
    resumo_apenas = False
    
    for doc in dados_parsed['docs']:
        schema = doc.get('schema', '')
        if 'procCTe' in schema:
            try:
                xml_conteudo = descompactar_base64_zip(doc['content_b64'])
            except Exception as e:
                return {'status': 'erro_compressao', 'mensagem': f"Incapaz de extrair B64 Base do ZIP: {str(e)}"}
        elif 'resCTe' in schema:
            resumo_apenas = True
            
    if xml_conteudo:
        return {'status': 'sucesso_xml', 'conteudo': xml_conteudo}
    elif resumo_apenas:
        return {'status': 'sucesso_resumo', 'mensagem': 'Retornado apenas resCTe. A transportadora bloqueou/não listou o acesso publicamente.'}
    else:
        return {'status': 'erro_schema', 'mensagem': 'Tag docZip retornada porém sem modelo procCTe/resCTe conhecido.'}
