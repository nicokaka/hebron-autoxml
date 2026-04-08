"""
Manifestação de Destinatário — Evento 210210 (Ciência da Operação)
Endpoint: NFeRecepcaoEvento4 (Ambiente Nacional)

Fluxo:
  1. Gera XML <evento> para cada chave
  2. Assina cada <evento> individualmente (XMLDSig, RSA-SHA1, C14N 1.0)
  3. Empacota em lotes de até 20 eventos por requisição SOAP 1.2
  4. Parseia a resposta por chave:
       cStat 135 = Registrado com sucesso
       cStat 573 = Duplicidade (inofensivo — já manifestado antes)
       Outros   = Erro, loga e continua
"""
import requests
import urllib3
from lxml import etree
from signxml import XMLSigner, methods
from typing import Callable, Dict

from src.core.triagem import dh_evento_local

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_NS_NFE   = "http://www.portalfiscal.inf.br/nfe"
_NS_WSDL  = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeRecepcaoEvento4"
_NS_SOAP  = "http://www.w3.org/2003/05/soap-envelope"
_NS_DSIG  = "http://www.w3.org/2000/09/xmldsig#"

_URL_PROD = "https://www.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx"
_URL_HOM  = "https://hom.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx"

_SOAP_ACTION = (
    'application/soap+xml; charset=utf-8; '
    'action="http://www.portalfiscal.inf.br/nfe/wsdl/NFeRecepcaoEvento4/nfeRecepcaoEvento"'
)


# ─── Passo 1: Gerar XML do evento (sem assinatura) ───────────────────────────

def _gerar_xml_evento(cnpj: str, chave: str, tp_amb: str) -> str:
    """
    Gera o bloco <evento> sem assinatura.
    Id = "ID210210" + chave(44) + "01"  ← sem nenhum dígito extra no meio
    """
    id_evento = f"ID210210{chave}01"
    dh = dh_evento_local()

    return (
        f'<evento xmlns="{_NS_NFE}" versao="1.00">'
        f'<infEvento Id="{id_evento}">'
        f'<cOrgao>91</cOrgao>'
        f'<tpAmb>{tp_amb}</tpAmb>'
        f'<CNPJ>{cnpj}</CNPJ>'
        f'<chNFe>{chave}</chNFe>'
        f'<dhEvento>{dh}</dhEvento>'
        f'<tpEvento>210210</tpEvento>'
        f'<nSeqEvento>1</nSeqEvento>'
        f'<verEvento>1.00</verEvento>'
        f'<detEvento versao="1.00">'
        f'<descEvento>Ciencia da Operacao</descEvento>'
        f'</detEvento>'
        f'</infEvento>'
        f'</evento>'
    )


# ─── Passo 2: Assinar o evento (XMLDSig) ─────────────────────────────────────

def _assinar_evento(xml_evento_str: str, cert_pem: bytes, key_pem: bytes) -> str:
    """
    Assina o bloco <evento> usando o snippet validado pelo especialista.

    Specs SEFAZ (Evento versao 1.00):
      - Digest:           SHA-1
      - Assinatura:       RSA-SHA1
      - Canonicalização:  C14N 1.0 (sem comentários)
      - Posição:          <Signature> dentro de <evento>, após </infEvento>

    Macete: injeta xml:id provisório para que signxml resolva a URI "#ID..."
    e remove após assinar para não causar rejeição de schema.

    IMPORTANTE: Não remover o prefixo ds: da <Signature> — SEFAZ aceita.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_evento_str.encode("utf-8"), parser)

    inf_evento = root.find(f"{{{_NS_NFE}}}infEvento")
    id_ref = inf_evento.get("Id")

    # Macete: ensina ao lxml/signxml que "Id" é uma âncora válida
    inf_evento.attrib["{http://www.w3.org/XML/1998/namespace}id"] = id_ref

    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha1",
        digest_algorithm="sha1",
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
    )

    signed_root = signer.sign(
        root,
        key=key_pem,
        cert=cert_pem,
        reference_uri=f"#{id_ref}",
    )

    # Remove o atributo temporário após assinar
    signed_inf = signed_root.find(f"{{{_NS_NFE}}}infEvento")
    xml_ns_id = "{http://www.w3.org/XML/1998/namespace}id"
    if xml_ns_id in signed_inf.attrib:
        del signed_inf.attrib[xml_ns_id]

    return etree.tostring(signed_root, encoding="unicode")


# ─── Passo 3: Montar envelope SOAP 1.2 ───────────────────────────────────────

def _montar_envelope(eventos_xml: list, id_lote: int, tp_amb: str) -> str:
    """
    Empacota até 20 <evento> assinados dentro de <envEvento> + SOAP 1.2.
    nfeDadosMsg vai direto no <Body> (sem wrapper adicional).
    """
    eventos_concat = "\n".join(eventos_xml)
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<soap12:Envelope xmlns:soap12="{_NS_SOAP}">'
        "<soap12:Body>"
        f'<nfeDadosMsg xmlns="{_NS_WSDL}">'
        f'<envEvento xmlns="{_NS_NFE}" versao="1.00">'
        f"<idLote>{id_lote}</idLote>"
        f"{eventos_concat}"
        "</envEvento>"
        "</nfeDadosMsg>"
        "</soap12:Body>"
        "</soap12:Envelope>"
    )


# ─── Passo 4: Parsear resposta ────────────────────────────────────────────────

def _parsear_resposta(resp_text: str) -> Dict[str, str]:
    """
    Parseia o <retEnvEvento> e retorna {chave: cStat} por evento.
    cStat 135 = registrado | cStat 573 = duplicidade (OK) | outros = erro
    """
    resultado = {}
    try:
        root = etree.fromstring(resp_text.encode("utf-8"))
        ns = {"nfe": _NS_NFE}
        for ret in root.iter(f"{{{_NS_NFE}}}retEvento"):
            inf = ret.find(f"{{{_NS_NFE}}}infEvento")
            if inf is None:
                continue
            chave_el = inf.find(f"{{{_NS_NFE}}}chNFe")
            cstat_el = inf.find(f"{{{_NS_NFE}}}cStat")
            if chave_el is not None and cstat_el is not None:
                resultado[chave_el.text] = cstat_el.text
    except Exception:
        pass
    return resultado


# ─── Função pública principal ─────────────────────────────────────────────────

def enviar_manifestacao(
    cert_path: str,
    key_path: str,
    cnpj: str,
    chaves: list,
    ambiente: str,
    on_progresso: Callable = None,
) -> Dict[str, str]:
    """
    Envia Ciência da Operação (210210) para uma lista de chaves NFe.

    - Divide em lotes de até 20 chaves por requisição.
    - Assina cada <evento> individualmente.
    - Retorna dict {chave: cStat} para cada chave enviada.
    - cStat 135 = sucesso, 573 = duplicidade (inofensivo), outros = erro.

    Args:
        cert_path: Caminho do .pem do certificado público.
        key_path:  Caminho do .pem da chave privada.
        cnpj:      CNPJ do destinatário (14 dígitos, sem pontuação).
        chaves:    Lista de chaves de 44 dígitos para manifestar.
        ambiente:  "producao" ou "homologacao".
        on_progresso: Callback de log (msg: str) → None.
    """
    if on_progresso is None:
        on_progresso = lambda msg: None

    tp_amb = "2" if ambiente.lower() == "homologacao" else "1"
    url = _URL_HOM if ambiente.lower() == "homologacao" else _URL_PROD
    headers = {"Content-Type": _SOAP_ACTION}
    headers["Accept"] = "application/soap+xml; charset=utf-8"

    # Lê cert/key em bytes para o signxml
    with open(cert_path, "rb") as f:
        cert_pem = f.read()
    with open(key_path, "rb") as f:
        key_pem = f.read()

    resultado_global: Dict[str, str] = {}
    tamanho_lote = 20

    lotes = [chaves[i: i + tamanho_lote] for i in range(0, len(chaves), tamanho_lote)]

    for idx_lote, lote in enumerate(lotes):
        on_progresso(
            f"[Manifestação] Enviando lote {idx_lote + 1}/{len(lotes)} "
            f"({len(lote)} chaves)..."
        )

        # Gerar e assinar cada evento do lote
        eventos_assinados = []
        for chave in lote:
            try:
                xml_evt = _gerar_xml_evento(cnpj, chave, tp_amb)
                xml_sign = _assinar_evento(xml_evt, cert_pem, key_pem)
                eventos_assinados.append(xml_sign)
            except Exception as e:
                on_progresso(f"[Manifestação] ⚠️ Erro ao assinar {chave[:20]}...: {e}")
                resultado_global[chave] = "ERRO_ASSINATURA"

        if not eventos_assinados:
            continue

        # Montar e enviar o envelope SOAP
        envelope = _montar_envelope(eventos_assinados, id_lote=idx_lote + 1, tp_amb=tp_amb)

        try:
            resp = requests.post(
                url,
                data=envelope.encode("utf-8"),
                headers=headers,
                cert=(cert_path, key_path),
                verify=False,
                timeout=30,
            )
            resultado_lote = _parsear_resposta(resp.text)
            resultado_global.update(resultado_lote)

            sucessos = sum(1 for v in resultado_lote.values() if v in ("135", "573"))
            on_progresso(
                f"[Manifestação] Lote {idx_lote + 1}: {sucessos}/{len(lote)} registrados "
                f"(135=ok, 573=duplicidade inofensiva)."
            )
        except Exception as e:
            on_progresso(f"[Manifestação] ⚠️ Erro de rede no lote {idx_lote + 1}: {e}")

    return resultado_global
