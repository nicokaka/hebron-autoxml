"""
Etapa 0.3: Teste do Serviço CTeDistribuicaoDFe por Chave.

Objetivo:
Validar o fluxo oficial de distribuição de CT-e (Conhecimento de Transporte)
pela chave informada e testar a viabilidade das credenciais para obtê-lo sob
a infraestrutura estrita do webservice oficial.
"""

import sys
import os
import argparse
import requests
from requests.exceptions import RequestException

import helpers

def payload_cte_distribuicao_chave(uf_autor: str, cnpj: str, chave: str, ambiente: str) -> str:
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

def consultar_sefaz_cte_chave(cert_path: str, key_path: str, uf_autor: str, cnpj: str, chave: str, ambiente: str) -> str:
    if ambiente.lower() == "homologacao":
        url = "https://hom1.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx"
    else:
        url = "https://www1.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx"
        
    headers = {
        'Content-Type': 'application/soap+xml; charset=utf-8',
        'SOAPAction': 'http://www.portalfiscal.inf.br/cte/wsdl/CTeDistribuicaoDFe/cteDistDFeInteresse'
    }
    
    payload = payload_cte_distribuicao_chave(uf_autor, cnpj, chave, ambiente)
    
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        resp = requests.post(url, data=payload, headers=headers, cert=(cert_path, key_path), verify=False, timeout=25)
        return resp.text
    except RequestException as e:
        raise ConnectionError(f"Erro mTLS: {e}")

def main():
    parser = argparse.ArgumentParser(description="Etapa 0.3: Consulta Pura de CT-e (via Chave em Distribuicao)")
    parser.add_argument("--pfx", required=True, help="Caminho para o arquivo .pfx")
    parser.add_argument("--senha", required=True, help="Senha")
    parser.add_argument("--chave-cte", required=True, help="Chave CT-e exata de 44 dígitos apenas números")
    parser.add_argument("--ambiente", default="producao", choices=["homologacao", "producao"], help="Use producao para testar chaves CTe reais.")
    parser.add_argument("--salvar-exemplo-dir", default=None, help="Pasta para salvar extração do XML")
    args = parser.parse_args()
    
    validado = []
    falhou = []
    
    if len(args.chave_cte) != 44 or not args.chave_cte.isdigit():
        falhou.append("Chave CT-e não atende aos requisitos formatados de 44 numerais.")
        helpers.print_relatorio("ERRO DE FILTRO", validado, falhou, "Passe exatamente a string limpa no CLI ('--chave-cte').")
        sys.exit(1)
        
    if not os.path.isfile(args.pfx):
        falhou.append(f"PFX inválido no ambiente: {args.pfx}")
        helpers.print_relatorio("FALHA DE DIRETÓRIO", validado, falhou, "Caminho inacessível.")
        sys.exit(1)

    try:
        priv_key, cert, _ = helpers.carregar_pfx(args.pfx, args.senha)
    except Exception:
        falhou.append("Erro de Decodificação PKCS#12.")
        helpers.print_relatorio("ERRO DE CERTIFICADO", validado, falhou, "A Senha incorreta ou formato corrompido paralisa o app.")
        sys.exit(2)
        
    metadados = helpers.extrair_metadados_certificado(cert)
    cnpj_base = metadados.get('cnpj_extraido')
    if not cnpj_base:
        falhou.append("Não foi resgatado via parser nenhum número limpo de CNPJ no .PFX para embutir na tag XML automaticamente.")
        cnpj_base = "00000000000000"
    else:
        validado.append(f"CNPJ Auto-Extraído do certificado para SOAP: {cnpj_base}")
        
    uf_autor = args.chave_cte[:2]
    validado.append(f"UF Originadora extrapolada da chave CT-e como '{uf_autor}'.")

    xml_retorno_bruto = ""
    with helpers.pfx_para_pem_temporario(priv_key, cert) as (cert_pem, key_pem):
        try:
            xml_retorno_bruto = consultar_sefaz_cte_chave(cert_pem, key_pem, uf_autor, cnpj_base, args.chave_cte, args.ambiente)
            validado.append(f"Conexão HTTPS superou o shield TLS perante DistDFe CT-e (Ambiente {args.ambiente}).")
        except ConnectionError as e:
            falhou.append(str(e))
            helpers.print_relatorio("FALHA DE REDE SEFAZ", validado, falhou, "O CTe da SEFAZ recusou fisicamente sua conexão. Revise IPs/Timeout.")
            sys.exit(3)
            
    dados = helpers.parse_retorno_distribuicao(xml_retorno_bruto, is_cte=True)
    
    if 'error' in dados:
        falhou.append(f"XML Parsing detectou erro severo: {dados['error']}")
        
        conclusao = "WS Nacional Rejeitou a Carga!"
        if "Schema" in dados['error'] or "Fault" in dados['error']:
            conclusao = "[MVP 1.1 = CT-e] SEFAZ recusa consulta 'consChCTe' neste Endpoint. Demanda varredura NSU."
            
        helpers.print_relatorio("CT-E INVIÁVEL POR CHAVE", validado, falhou, conclusao)
        sys.exit(4)

    validado.append(f"CTe Parsing cStat: {dados['cStat']}, xMotivo: {dados['xMotivo']}")

    tem_xml_puro = False
    tem_resumo = False
    
    if dados['docs']:
        validado.append(f"Docs acoplados na resposta: {len(dados['docs'])} items.")
        
        if args.salvar_exemplo_dir:
            try:
                os.makedirs(args.salvar_exemplo_dir, exist_ok=True)
            except OSError:
                pass
            
        for doc in dados['docs']:
            schema = doc.get('schema', 'unknown')
            if 'procCTe' in schema:
                tem_xml_puro = True
                validado.append("XML Completo CTe (procCTe) reconhecido dentro do ZIP.")
            elif 'resCTe' in schema:
                tem_resumo = True
                validado.append("Apenas resumo (resCTe) reconhecido.")
                
            try:
                if args.salvar_exemplo_dir:
                    nome_arq = f"cte_{schema.replace('.xsd','')}_{args.chave_cte}.xml"
                    path = os.path.join(args.salvar_exemplo_dir, nome_arq)
                    xml_puro = helpers.descompactar_base64_zip(doc['content_b64'])
                    with open(path, 'w', encoding='utf-8') as fs:
                        fs.write(xml_puro)
                    validado.append(f"Arquivo zip descompactado => {path}")
            except Exception as e:
                falhou.append(f"Falha gravadação HD/Deflate: {e}")
    else:
        falhou.append("Nenhum CT-e zipado acoplado no lote (cStat = 137).")
        
    conclusao_final = "CT-E NÃO LOCALIZADO / STATUS CSTAT BRUTO."
    if tem_xml_puro:
        conclusao_final = "[MVP 1 = NF-e + CT-e] Sucesso Extremo. CT-e full extraído sem atritos via chave."
    elif tem_resumo:
        conclusao_final = "[MVP 1.1 = CT-e] O Emissor travou o CT-e full e só resumos pingaram. Complexador engatilhado."
    else:
        conclusao_final = "[MVP 1 = SÓ NF-e; CTe = MVP 1.1] Resposta não-nula, porém seca. Sem docZip retornável via Busca Simples de Chave."
        
    helpers.print_relatorio("VEREDITO DO CT-E", validado, falhou, conclusao_final)
    sys.exit(0)

if __name__ == "__main__":
    main()
