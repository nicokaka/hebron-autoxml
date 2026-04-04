"""
Etapa 0.1: Teste e Validação Avançada de Certificado Digital (.pfx).

Objetivo:
Validar de forma explícita arquivo PFX via linha de comando, analisar datas,
extrair documentação e provar conectividade HTTPS mTLS via requests com a SEFAZ.
"""

import os
import sys
import argparse
import datetime
import requests
from requests.exceptions import RequestException

import helpers

def testar_conexao_sefaz(cert_path: str, key_path: str) -> bool:
    url = "https://nfe-homologacao.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx"
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resposta = requests.get(url, cert=(cert_path, key_path), verify=False, timeout=15)
        # Sefaz retorna HTTP 200 (se GET manual) ou 400. Se chegou aqui, SSL Handshake ocorreu perfeitamente.
        if resposta.status_code:
            return True
        return False
    except RequestException:
        return False

def main() -> None:
    parser = argparse.ArgumentParser(description="Etapa 0.1: Teste A1 PFX e conectividade SEFAZ")
    parser.add_argument("--pfx", required=True, help="Caminho relativo ou absoluto para o arquivo .pfx")
    parser.add_argument("--senha", required=True, help="Senha do arquivo .pfx")
    
    args = parser.parse_args()
    
    validado = []
    falhou = []
    
    if not os.path.isfile(args.pfx):
        falhou.append(f"Arquivo PFX inexistente em: {args.pfx}")
        helpers.print_relatorio("FALHA NA ABERTURA", validado, falhou, "Certifique-se do caminho usando as aspas e tente novamente.")
        sys.exit(1)
        
    validado.append("Arquivo PFX encontrado no disco.")
    
    try:
        priv_key, cert, _ = helpers.carregar_pfx(args.pfx, args.senha)
        validado.append("Senha correta. Chaves desencapsuladas temporalmente na memória (Decodificação PKCS#12).")
    except ValueError:
        falhou.append("Senha incorreta ou pacote PFX mal formatado (ValueError - Mac Verify).")
        helpers.print_relatorio("FALHA DE DESCRIPTOGRAFIA", validado, falhou, "A senha fornecida falhou ao abrir o cofre A1 PFX.")
        sys.exit(2)
    except Exception as e:
        falhou.append(f"Erro estrutural no PFX: {str(e)}")
        helpers.print_relatorio("FALHA ESTRUTURAL", validado, falhou, "O certificado não usou os padrões ICP-Brasil / OpenSSL esperados.")
        sys.exit(2)
        
    try:
        metadados = helpers.extrair_metadados_certificado(cert)
        validado.append("Extração de metadados legíveis consumada sem exceções.")
    except Exception as e:
        falhou.append(f"Falha ao destrinchar propriedades e OIDs estruturais da árvore: {str(e)}")
        helpers.print_relatorio("FALHA NOS METADADOS", validado, falhou, "Não foi possível resgatar validades ou CNPJ do Subject.")
        sys.exit(2)
    
    # Tratamentos Seguros de Fuso e Validade
    agora = datetime.datetime.now(datetime.timezone.utc)
    data_inicio = metadados['validade_inicial']
    data_fim = metadados['validade_final']
    if not hasattr(data_fim, 'tzinfo') or data_fim.tzinfo is None:
        agora = datetime.datetime.utcnow()
        
    cert_ativo = True
    if agora < data_inicio:
        falhou.append(f"O certificado ainda não alcançou vigência. Vigora apenas a partir de: {data_inicio}")
        cert_ativo = False
    elif agora > data_fim:
        falhou.append(f"Certificado Digital Expirado na data de: {data_fim}")
        cert_ativo = False
    else:
        validado.append(f"Certificado ativo e usável. (Válido de {data_inicio} até {data_fim})")
        
    if not cert_ativo:
        helpers.print_relatorio("FALHA DE VIGÊNCIA", validado, falhou, "Substitua o certificado pfx atual por um recém-assinado ou revogado.")
        sys.exit(2)
        
    # Exposição Cautelosa 
    if metadados['cnpj_extraido']:
        validado.append(f"CNPJ Autor foi extraído indiretamente dos OIDs intrínsecos como: {metadados['cnpj_extraido']}")
    else:
        falhou.append("O PFX não disponibiliza o CPNJ base em campo público. O robô exigirá inserção hardcoded.")

    # Conexão (Timeout)
    with helpers.pfx_para_pem_temporario(priv_key, cert) as (cert_p, key_p):
        sucesso = testar_conexao_sefaz(cert_p, key_p)
        
    if sucesso:
        validado.append("Handshake TLS com uso Exclusivo de Criptografia Cliente-mTLS perante a SEFAZ fluiu (Sem barreiras/Firewall local).")
        helpers.print_relatorio(
            "SUCESSO ABSOLUTO", 
            validado, 
            falhou, 
            "Certificado 100% legível, sadio e que fala a linguagem TLS/Web da Fazenda sem timeout. Gate número 1 transposto!"
        )
        sys.exit(0)
    else:
        falhou.append("Falha gravíssima ao estabelecer sessão criptografada mTLS. Rede caiu ou a autarquia negou porta 443.")
        helpers.print_relatorio(
            "FALHA DE COMUNICAÇÕES EXTERNAS", 
            validado, 
            falhou, 
            "Desligue Firewalls, Anti-Virus agressivos ou recheque as conexões. Os gateways SVRS homolog não pingam SSL local."
        )
        sys.exit(3)

if __name__ == "__main__":
    main()
