"""
Módulo de funções auxiliares (Helpers) para o projeto HebronAutoXML.

Aqui encontram-se as abstrações utilitárias mínimas para manipular certificados,
fazer requests (mTLS) provisórios sem depender de adaptações robustas 
e processamentos genéricos de base64 e parsing de retorno (XML).
"""

import os
import re
import tempfile
import contextlib
import base64
import zlib
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Any, Tuple
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization

def console_out(msg: str, status: str = "INFO") -> None:
    """Helper simples para output padronizado no console."""
    print(f"[{status}] {msg}")

def carregar_pfx(caminho_pfx: str, senha: str) -> Tuple[Any, Any, list[Any]]:
    with open(caminho_pfx, "rb") as f:
        pfx_data = f.read()
    return pkcs12.load_key_and_certificates(pfx_data, senha.encode("utf-8"))

def extrair_cnpj_subject(subject_dicionario: Dict[str, str]) -> Optional[str]:
    for _, valor in subject_dicionario.items():
        valor_str = str(valor)
        match_sufixo = re.search(r':(\d{14})$', valor_str)
        if match_sufixo:
            return match_sufixo.group(1)
            
        match_direto = re.search(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b', valor_str)
        if match_direto:
            return re.sub(r'\D', '', match_direto.group())
            
    return None

def extrair_metadados_certificado(certificado: Any) -> Dict[str, Any]:
    subject_dict = {}
    for attr in certificado.subject:
        key = getattr(attr.oid, "_name", "OID_DESCONHECIDO")
        subject_dict[key] = str(attr.value)

    issuer_dict = {}
    for attr in certificado.issuer:
        key = getattr(attr.oid, "_name", "OID_DESCONHECIDO")
        issuer_dict[key] = str(attr.value)

    valido_de = getattr(certificado, 'not_valid_before_utc', getattr(certificado, 'not_valid_before', None))
    valido_ate = getattr(certificado, 'not_valid_after_utc', getattr(certificado, 'not_valid_after', None))

    return {
        "subject": subject_dict,
        "issuer": issuer_dict,
        "validade_inicial": valido_de,
        "validade_final": valido_ate,
        "serial_number": certificado.serial_number,
        "cnpj_extraido": extrair_cnpj_subject(subject_dict)
    }

@contextlib.contextmanager
def pfx_para_pem_temporario(private_key: Any, certificate: Any):
    fd_cert, cert_path = tempfile.mkstemp(suffix=".pem")
    fd_key, key_path = tempfile.mkstemp(suffix=".pem")
    
    try:
        with open(cert_path, "wb") as f_cert:
            f_cert.write(certificate.public_bytes(serialization.Encoding.PEM))
            
        with open(key_path, "wb") as f_key:
            f_key.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        yield cert_path, key_path
    finally:
        os.close(fd_cert)
        os.close(fd_key)
        
        if os.path.exists(cert_path):
            os.remove(cert_path)
        if os.path.exists(key_path):
            os.remove(key_path)

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

def parse_retorno_distribuicao(xml_text: str, is_cte: bool = False) -> Dict[str, Any]:
    """
    Utilitário purista para ler o envelope SOAP de resposta dos webservices.
    Identifica falhas de schema ou lote de documentos de retorno.
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
        # Avalia falhas estritas (SOAP Fault) indicativo de Erro de Certificado ou Serviço/Schema
        fault = root.find('.//soap:Fault', namespaces=ns)
        if fault is not None:
            text_node = fault.find('.//soap:Text', namespaces=ns)
            return {'error': f"SOAP Fault detectado: {text_node.text if text_node is not None else 'Erro desconhecido'}."}
        return {'error': 'Tag retDistDFeInt não encontrada no envelope e sem SOAP fault legível!'}
        
    cStat_tag = retorno.find('dfe:cStat', namespaces=ns)
    xMotivo_tag = retorno.find('dfe:xMotivo', namespaces=ns)
    ultNSU_tag = retorno.find('dfe:ultNSU', namespaces=ns)
    maxNSU_tag = retorno.find('dfe:maxNSU', namespaces=ns)
    
    docs = []
    lote = retorno.find('dfe:loteDistDFeInt', namespaces=ns)
    if lote is not None:
        for doc in lote.findall('dfe:docZip', namespaces=ns):
            docs.append({
                'NSU': doc.get('NSU'),
                'schema': doc.get('schema'),
                'content_b64': doc.text
            })
            
    return {
        'cStat': cStat_tag.text if cStat_tag is not None else None,
        'xMotivo': xMotivo_tag.text if xMotivo_tag is not None else None,
        'ultNSU': ultNSU_tag.text if ultNSU_tag is not None else None,
        'maxNSU': maxNSU_tag.text if maxNSU_tag is not None else None,
        'docs': docs
    }
