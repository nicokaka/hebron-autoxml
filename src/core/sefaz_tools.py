import base64
import zlib
import xml.etree.ElementTree as ET
from typing import Dict, Any

def descompactar_base64_zip(zip_b64: str) -> str:
    """
    Decodifica base64 e descompacta GZIP.
    Retorna a string do XML original extraída do docZip da SEFAZ.
    """
    dados_zipados = base64.b64decode(zip_b64)
    try:
        # 16 + MAX_WBITS aceita GZIP padrão
        dados_xml = zlib.decompress(dados_zipados, 16 + zlib.MAX_WBITS)
    except zlib.error:
        # Fallback raw deflate
        dados_xml = zlib.decompress(dados_zipados)
    return dados_xml.decode('utf-8', errors='replace')

def obter_chave_interna(xml_conteudo: str) -> str:
    """Tenta extrair de forma robusta o ID (chave 44 dígitos) de dentro do XML lido."""
    try:
        root = ET.fromstring(xml_conteudo)
    except ET.ParseError:
        return "PARSING_ERROR"
        
    for element in root.iter():
        tag_match = element.tag.split("}")[-1]
        if tag_match == "chNFe" or tag_match == "chCTe":
            return element.text or "SemTexto"
        if (tag_match == "infNFe" or tag_match == "infCte") and 'Id' in element.attrib:
            return element.attrib['Id'].replace('NFe', '').replace('CTe', '')
    return "CHAVE_NAO_LOCALIZADA"

def parse_retorno_distribuicao(xml_text: str, is_cte: bool = False) -> Dict[str, Any]:
    """
    Utilitário purista para ler o envelope SOAP de resposta cStat e xMotivo.
    """
    if xml_text.startswith('\ufeff'):
        xml_text = xml_text[1:]
        
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {'error': 'O servidor retornou uma resposta incodificável (não-XML).'}

    ns_tag = 'http://www.portalfiscal.inf.br/cte' if is_cte else 'http://www.portalfiscal.inf.br/nfe'
    ns = {
        'soap': 'http://www.w3.org/2003/05/soap-envelope', 
        'dfe': ns_tag
    }
    
    retorno = root.find('.//dfe:retDistDFeInt', namespaces=ns)
    
    if retorno is None:
        fault = root.find('.//soap:Fault', namespaces=ns)
        if fault is not None:
            text_node = fault.find('.//soap:Text', namespaces=ns)
            return {'error': f"SOAP Fault detectado: {text_node.text if text_node is not None else 'Erro desconhecido'}."}
        return {'error': 'Tag retDistDFeInt não encontrada no envelope.'}
        
    cStat_tag = retorno.find('dfe:cStat', namespaces=ns)
    xMotivo_tag = retorno.find('dfe:xMotivo', namespaces=ns)
    
    docs = []
    lote = retorno.find('dfe:loteDistDFeInt', namespaces=ns)
    if lote is not None:
        for doc in lote.findall('dfe:docZip', namespaces=ns):
            docs.append({
                'NSU': doc.get('NSU', ''),
                'schema': doc.get('schema', ''),
                'content_b64': doc.text
            })
            
    return {
        'cStat': cStat_tag.text if cStat_tag is not None else None,
        'xMotivo': xMotivo_tag.text if xMotivo_tag is not None else None,
        'docs': docs
    }
