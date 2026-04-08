import requests
from requests.exceptions import RequestException
from src.core.sefaz_tools import parse_retorno_distribuicao

def _payload_distnsu(uf_autor: str, cnpj: str, ult_nsu: str, ambiente: str) -> str:
    tp_amb = "2" if ambiente.lower() == "homologacao" else "1"
    
    # Preenche com zeros à esquerda até 15 dígitos
    ult_nsu = str(ult_nsu).zfill(15)
    
    tag_uf = f"          <cUFAutor>{uf_autor}</cUFAutor>\n" if uf_autor else ""
    
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
      <nfeDadosMsg>
        <distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
          <tpAmb>{tp_amb}</tpAmb>
{tag_uf}          <CNPJ>{cnpj}</CNPJ>
          <distNSU>
            <ultNSU>{ult_nsu}</ultNSU>
          </distNSU>
        </distDFeInt>
      </nfeDadosMsg>
    </nfeDistDFeInteresse>
  </soap12:Body>
</soap12:Envelope>"""

def baixar_lote_nsu(cert_path: str, key_path: str, uf_autor: str, cnpj: str, ult_nsu: str, ambiente: str) -> dict:
    """
    Retorna o payload parseado incluindo 'cStat', 'docs', 'ultNSU', 'maxNSU' e erros se existirem.
    """
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
    
    payload = _payload_distnsu(uf_autor, cnpj, ult_nsu, ambiente)
    
    try:
        resp = requests.post(url, data=payload, headers=headers, cert=(cert_path, key_path), verify=False, timeout=30)
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
        
    # cStat 137: Nenhum documento encontrado
    # cStat 138: Documento(s) localizado(s)
    
    # Prioridade máxima: bloqueio por consumo indevido. O cStat 656 pode vir com 137 ou docs corrompidos.
    if cStat == "656":
        return {'status': 'rejeitado_656', 'mensagem': xMotivo, 'ultNSU': dados_parsed.get('ultNSU', ult_nsu), 'maxNSU': dados_parsed.get('maxNSU', ult_nsu)}
        
    if cStat == "137" or not dados_parsed.get('docs'):
        return {'status': 'vazio', 'mensagem': f"{cStat} - {xMotivo}", 'ultNSU': dados_parsed.get('ultNSU', ult_nsu), 'maxNSU': dados_parsed.get('maxNSU', ult_nsu)}
        
    return {
        'status': 'sucesso',
        'cStat': cStat,
        'mensagem': xMotivo,
        'ultNSU': dados_parsed.get('ultNSU', '0'),
        'maxNSU': dados_parsed.get('maxNSU', '0'),
        'docs': dados_parsed.get('docs', [])
    }
