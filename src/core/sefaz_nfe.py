import requests
from requests.exceptions import RequestException

from src.core.sefaz_tools import descompactar_base64_zip, parse_retorno_distribuicao

def _payload_nfe_chave(uf_autor: str, cnpj: str, chave: str, ambiente: str) -> str:
    tp_amb = "2" if ambiente.lower() == "homologacao" else "1"
    tag_uf = f"          <cUFAutor>{uf_autor}</cUFAutor>\n" if uf_autor else ""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
      <nfeDadosMsg>
        <distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">
          <tpAmb>{tp_amb}</tpAmb>
{tag_uf}          <CNPJ>{cnpj}</CNPJ>
          <consChNFe>
            <chNFe>{chave}</chNFe>
          </consChNFe>
        </distDFeInt>
      </nfeDadosMsg>
    </nfeDistDFeInteresse>
  </soap12:Body>
</soap12:Envelope>"""

def consultar_nfe_chave(cert_path: str, key_path: str, uf_autor: str, cnpj: str, chave: str, ambiente: str) -> dict:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    if ambiente.lower() == "homologacao":
        url = "https://hom.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
    else:
        url = "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
        
    headers = {
        'Content-Type': 'application/soap+xml; charset=utf-8',
        'SOAPAction': 'http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe/nfeDistDFeInteresse'
    }
    
    payload = _payload_nfe_chave(uf_autor, cnpj, chave, ambiente)
    
    try:
        resp = requests.post(url, data=payload, headers=headers, cert=(cert_path, key_path), verify=False, timeout=25)
        resp_text = resp.text
    except RequestException as e:
        return {'status': 'erro_rede', 'mensagem': f"Time-Out ou bloqueio TLS: {str(e)}"}
        
    dados_parsed = parse_retorno_distribuicao(resp_text, is_cte=False)
    
    if 'error' in dados_parsed:
        return {'status': 'erro_soap', 'mensagem': dados_parsed['error']}
        
    
    cStat = dados_parsed.get('cStat')
    xMotivo = dados_parsed.get('xMotivo', 'Erro na Sefaz')
    
    if cStat is None:
        return {'status': 'erro_soap', 'mensagem': "O servidor não retornou a tag cStat esperada no XML."}
        
    if cStat == "137":
        return {'status': 'nao_encontrada', 'mensagem': "Nenhum documento encontrado (cStat 137)."}
        
    if not dados_parsed['docs']:
        return {'status': 'rejeitado', 'mensagem': f"cStat {cStat} retornado sem documentos limpos: {xMotivo}"}
        
    xml_conteudo = None
    resumo_apenas = False
    
    for doc in dados_parsed['docs']:
        schema = doc.get('schema', '')
        if 'procNFe' in schema:
            try:
                xml_conteudo = descompactar_base64_zip(doc['content_b64'])
            except Exception as e:
                return {'status': 'erro_compressao', 'mensagem': f"GZip corrompido ou erro Deflate: {str(e)}"}
        elif 'resNFe' in schema:
            resumo_apenas = True
            
    if xml_conteudo:
        return {'status': 'sucesso_xml', 'conteudo': xml_conteudo}
    elif resumo_apenas:
        return {'status': 'sucesso_resumo', 'mensagem': 'A SEFAZ retornou apenas o resumo. Exige Ciência da Operação.'}
    else:
        return {'status': 'erro_schema', 'mensagem': 'Nenhum schema procNFe/resNFe retornado dentro do zip lido.'}
