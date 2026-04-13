"""
Diagnostico: verifica se a assinatura RSA-SHA1 da manifestacao esta correta.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import base64
import hashlib
from lxml import etree

from src.core.sefaz_manifestacao import _gerar_xml_evento, _NS_NFE, _NS_DSIG

CHAVE_TESTE = "25260308540403000135550010001125101006010713"
CNPJ_TESTE  = "08939548000103"
TP_AMB      = "1"

def main():
    print("=" * 80)
    print("DIAGNOSTICO DE ASSINATURA")
    print("=" * 80)

    xml_evento = _gerar_xml_evento(CNPJ_TESTE, CHAVE_TESTE, TP_AMB)

    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_evento.encode("utf-8"), parser)
    inf_evento = root.find(f"{{{_NS_NFE}}}infEvento")

    # C14N INCLUSIVE (o que nosso codigo faz)
    c14n_inc = etree.tostring(inf_evento, method="c14n", exclusive=False, with_comments=False)
    digest_inc = base64.b64encode(hashlib.sha1(c14n_inc).digest()).decode()

    # C14N EXCLUSIVE (alternativa)
    c14n_exc = etree.tostring(inf_evento, method="c14n", exclusive=True, with_comments=False)
    digest_exc = base64.b64encode(hashlib.sha1(c14n_exc).digest()).decode()

    print("\n[INCLUSIVE C14N]:")
    print(c14n_inc.decode("utf-8"))
    print(f"\nDigest: {digest_inc}")

    print("\n[EXCLUSIVE C14N]:")
    print(c14n_exc.decode("utf-8"))
    print(f"\nDigest: {digest_exc}")

    if digest_inc != digest_exc:
        print("\n>>> DIGESTS SAO DIFERENTES! <<<")
        # Mostrar a diferenca exata
        inc_str = c14n_inc.decode("utf-8")
        exc_str = c14n_exc.decode("utf-8")
        # Encontrar onde divergem
        for i, (a, b) in enumerate(zip(inc_str, exc_str)):
            if a != b:
                print(f"\nDivergencia na posicao {i}:")
                print(f"  Inclusive: ...{inc_str[max(0,i-30):i+50]}...")
                print(f"  Exclusive: ...{exc_str[max(0,i-30):i+50]}...")
                break
    else:
        print("\n>>> DIGESTS SAO IDENTICOS <<<")

    # Verificar no contexto SOAP
    print("\n" + "=" * 80)
    print("VERIFICACAO NO CONTEXTO SOAP")
    print("=" * 80)

    envelope_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        '<soap12:Body>'
        '<nfeDadosMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeRecepcaoEvento4">'
        '<envEvento xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">'
        '<idLote>1</idLote>'
        f'{xml_evento}'
        '</envEvento>'
        '</nfeDadosMsg>'
        '</soap12:Body>'
        '</soap12:Envelope>'
    )

    root_soap = etree.fromstring(envelope_xml.encode("utf-8"), parser)
    inf_in_soap = None
    for el in root_soap.iter(f"{{{_NS_NFE}}}infEvento"):
        inf_in_soap = el
        break

    c14n_soap_inc = etree.tostring(inf_in_soap, method="c14n", exclusive=False, with_comments=False)
    digest_soap_inc = base64.b64encode(hashlib.sha1(c14n_soap_inc).digest()).decode()

    c14n_soap_exc = etree.tostring(inf_in_soap, method="c14n", exclusive=True, with_comments=False)
    digest_soap_exc = base64.b64encode(hashlib.sha1(c14n_soap_exc).digest()).decode()

    print(f"\n[SOAP + INCLUSIVE C14N]:")
    print(c14n_soap_inc.decode("utf-8"))
    print(f"Digest: {digest_soap_inc}")

    print(f"\n[SOAP + EXCLUSIVE C14N]:")
    print(c14n_soap_exc.decode("utf-8"))
    print(f"Digest: {digest_soap_exc}")

    print("\n" + "=" * 80)
    print("RESUMO DE COMPATIBILIDADE")
    print("=" * 80)
    print(f"Standalone Inclusive: {digest_inc}")
    print(f"Standalone Exclusive: {digest_exc}")
    print(f"SOAP Inclusive:       {digest_soap_inc}")
    print(f"SOAP Exclusive:      {digest_soap_exc}")

    if digest_inc == digest_soap_inc:
        print("\nStandalone Inc == SOAP Inc: OK")
    else:
        print("\nStandalone Inc != SOAP Inc: DIVERGE (causa potencial do 297)")

    if digest_exc == digest_soap_exc:
        print("Standalone Exc == SOAP Exc: OK")
    else:
        print("Standalone Exc != SOAP Exc: DIVERGE")


if __name__ == "__main__":
    main()
