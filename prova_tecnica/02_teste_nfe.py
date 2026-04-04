"""
Etapa 0.2: Teste do Serviço NFeDistribuicaoDFe.

Objetivo:
Validar o fluxo oficial de distribuição de Documentos Fiscais Eletrônicos via SEFAZ Nacional.
Recebe base de credenciais, conecta no serviço (produção ou homol), baixa um lote usando
ultNSU=0 para mapear a funcionalidade da rede e identificar schemas (chaves / procNFe / resNFe).
"""

import sys
import os
import argparse
import requests
import xml.etree.ElementTree as ET
from requests.exceptions import RequestException
import helpers

def payload_nfe_distribuicao(uf_autor: str, cnpj: str, ambiente: str) -> str:
    tp_amb = "2" if ambiente.lower() == "homologacao" else "1"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
      <nfeDadosMsg>
        <distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.38">
          <tpAmb>{tp_amb}</tpAmb>
          <cUFAutor>{uf_autor}</cUFAutor>
          <CNPJ>{cnpj}</CNPJ>
          <distNSU>
            <ultNSU>000000000000000</ultNSU>
          </distNSU>
        </distDFeInt>
      </nfeDadosMsg>
    </nfeDistDFeInteresse>
  </soap12:Body>
</soap12:Envelope>"""

def consultar_sefaz_distribuicao(cert_path: str, key_path: str, uf_autor: str, cnpj: str, ambiente: str) -> str:
    if ambiente.lower() == "homologacao":
        url = "https://hom.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
    else:
        url = "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
        
    headers = {
        'Content-Type': 'application/soap+xml; charset=utf-8',
        'SOAPAction': 'http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe/nfeDistDFeInteresse'
    }
    
    payload = payload_nfe_distribuicao(uf_autor, cnpj, ambiente)
    
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        resp = requests.post(url, data=payload, headers=headers, cert=(cert_path, key_path), verify=False, timeout=25)
        return resp.text
    except RequestException as e:
        raise ConnectionError(f"HTTP/TLS RequestException: {e}")

def tentar_obter_chave_xml(xml_conteudo: str) -> str:
    try:
        root = ET.fromstring(xml_conteudo)
    except ET.ParseError:
        return "PARSING_ERROR"
        
    for element in root.iter():
        tag_match = element.tag.split("}")[-1]
        if tag_match == "chNFe":
            return element.text or "SemTexto"
        if tag_match == "infNFe" and 'Id' in element.attrib:
            return element.attrib['Id'].replace('NFe', '')
    return "CHAVE_NAO_LOCALIZADA"

def main():
    parser = argparse.ArgumentParser(description="Etapa 0.2: Consulta de Distribuição Pura NF-e e Schemas")
    parser.add_argument("--pfx", required=True, help="Caminho relativo/absoluto PFX")
    parser.add_argument("--senha", required=True, help="Senha")
    parser.add_argument("--uf-autor", required=True, help="Código IBGE UF Solicitante (Ex: 35)")
    parser.add_argument("--ambiente", default="producao", choices=["homologacao", "producao"], help="Use producao para ter volume de notas real de terceiros.")
    parser.add_argument("--cnpj-base", required=True, help="CNPJ puro (Exato 14 dígitos numéricos)")
    parser.add_argument("--salvar-exemplo-dir", default=None, help="Pasta para depósito de XML full extraído puramente.")
    args = parser.parse_args()
    
    validado = []
    falhou = []
    
    if len(args.cnpj_base) != 14 or not args.cnpj_base.isdigit():
        falhou.append(f"CNPJ inserido inválido: '{args.cnpj_base}'.")
        helpers.print_relatorio("FALHA DE PARÂMETRO", validado, falhou, "O CNPJ na distribuição precisa ter exatamente 14 numerais limpos/sem máscaras.")
        sys.exit(1)

    if not os.path.isfile(args.pfx):
        falhou.append(f"Caminho PFX estritamente não encontrado: {args.pfx}")
        helpers.print_relatorio("FALHA DE OPERAÇÃO", validado, falhou, "Mova o arquivo ou reordene o caminho indicado.")
        sys.exit(1)

    try:
        priv_key, cert, _ = helpers.carregar_pfx(args.pfx, args.senha)
    except Exception:
        falhou.append("Rejeição da Sefaz Criptográfica (Senha/Corrupção no arquivo base).")
        helpers.print_relatorio("FALHA DE COMPACTAÇÃO CERTIFICADO", validado, falhou, "O pfx encontra-se atipicamente barrado ao OpenSSL nativo Python.")
        sys.exit(2)
        
    validado.append("Base PFX e metadados lidos em contexto de isolamento de memória.")
        
    xml_retorno_bruto = ""
    with helpers.pfx_para_pem_temporario(priv_key, cert) as (cert_pem, key_pem):
        try:
            xml_retorno_bruto = consultar_sefaz_distribuicao(cert_pem, key_pem, args.uf_autor, args.cnpj_base, args.ambiente)
            validado.append(f"Conexão consolidada no WS de Distribuição sem expirar o request. (Ambiente: {args.ambiente})")
        except ConnectionError as e:
            falhou.append(str(e))
            helpers.print_relatorio("ERRO DE REDE BRUTA", validado, falhou, "A SEFAZ ou seu IP recusaram acesso e a requisição morreu por timeout/restrição de rede.")
            sys.exit(3)
            
    dados_parsed = helpers.parse_retorno_distribuicao(xml_retorno_bruto, is_cte=False)
    
    if 'error' in dados_parsed:
        falhou.append(f"Parsing do envelope falhou (Línguagem base não decifrável): {dados_parsed['error']}")
        helpers.print_relatorio("ERRO SOAP OU SCHEMA", validado, falhou, "Sefaz não reconhece autor, tag ou layout. Avalie as informações atreladas e regras fiscais.")
        sys.exit(4)
        
    validado.append(f"Leitura de Carga Útil finalizou: cStat = {dados_parsed['cStat']}, xMotivo = '{dados_parsed['xMotivo']}'")
    
    # Trackers do tipo de Documento Analisador para o MVP
    obteve_proc = False
    obteve_res = False
    
    if dados_parsed['docs']:
        validado.append(f"SEFAZ cuspiu array contendo {len(dados_parsed['docs'])} pacote(s) compactados base64.")
    
        if args.salvar_exemplo_dir:
            try:
                os.makedirs(args.salvar_exemplo_dir, exist_ok=True)
            except OSError:
                pass 
            
        salvou = False
        for doc in dados_parsed['docs']:
            schema = str(doc.get("schema", "desconhecido"))
            if "procNFe" in schema:
                obteve_proc = True
            elif "resNFe" in schema:
                obteve_res = True
                
            if args.salvar_exemplo_dir and not salvou:
                try:
                    xml_puro = helpers.descompactar_base64_zip(doc['content_b64'])
                    chave_detectada = tentar_obter_chave_xml(xml_puro)
                    path = os.path.join(args.salvar_exemplo_dir, f"nfe_exemplo_nsu_{doc['NSU']}_{chave_detectada}.xml")
                    with open(path, 'w', encoding='utf-8') as fs:
                        fs.write(xml_puro)
                    validado.append(f"Sucesso ao injetar {schema} legível como RAW FILE em: {path}")
                    salvou = True
                except Exception as e:
                    falhou.append(f"I/O Falido ou problema no Deflate ao cuspir schema [{schema}]: {e}")
    else:
        falhou.append("Nenhum dado com docZip embutido foi retornado (Comum se cStat for 137 - Nenhum documento localizado ou fila vazia).")

    # Árvore de Decisão de Backend / MVP
    conclusao = "INCONCLUSIVO."
    if dados_parsed['cStat'] == "137":
         conclusao = "Fila SEFAZ Nacional limpa. Nenhum XML extraível no momento. Tente com CNPJ de maior volumetria."
    elif str(dados_parsed['cStat']) not in ["138", "137"]:
         conclusao = f"Falha Regimental Estrutural. cStat retornado [{dados_parsed['cStat']}]. Possível Bloqueio de IE ou erro de credenciais."
    elif obteve_proc:
         conclusao = "[MVP 1 = NF-e Completa] Recebemos notas procNFe puras! Extrator pode colher direto, dispensando 'Ciência da Operação'."
    elif obteve_res:
         conclusao = "[MVP 1 = NF-e + Manifestação Obrigatória] Recebemos resNFe. A SEFAZ mandou resumos e obriga MDe de Ciência de Operação para o download final."

    helpers.print_relatorio("ROTA NF-e CONCLUÍDA", validado, falhou, conclusao)
    sys.exit(0)

if __name__ == "__main__":
    main()
