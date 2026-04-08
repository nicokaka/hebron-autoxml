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
import os
import base64
import hashlib
from datetime import datetime
import requests
import urllib3
from lxml import etree
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography import x509
from typing import Callable, Dict

from src.core.triagem import dh_evento_local

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── Diagnóstico SEFAZ ───────────────────────────────────────────────────────
_DIAG_DIR = os.path.join(os.path.expanduser("~"), ".HebronAutoXML")
_DIAG_FILE_MANIF = os.path.join(_DIAG_DIR, "diagnostico_manifestacao.log")

def _dump_diagnostico_manif(lote_idx: int, payload: str, status_code: int, response_text: str):
    """Grava em arquivo o XML enviado e a resposta crua da SEFAZ para debugging."""
    try:
        os.makedirs(_DIAG_DIR, exist_ok=True)
        with open(_DIAG_FILE_MANIF, "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{'='*80}\n")
            f.write(f"[{ts}] LOTE: {lote_idx}\n")
            f.write(f"--- PAYLOAD ENVIADO ---\n{payload[:3000]}\n...\n")
            f.write(f"--- RESPOSTA SEFAZ (HTTP {status_code}) ---\n{response_text}\n")
    except Exception:
        pass  # Nunca deixar o diagnóstico quebrar o fluxo principal

_NS_NFE   = "http://www.portalfiscal.inf.br/nfe"
_NS_WSDL  = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeRecepcaoEvento4"
_NS_SOAP  = "http://www.w3.org/2003/05/soap-envelope"
_NS_DSIG  = "http://www.w3.org/2000/09/xmldsig#"
_C14N_ALG = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"

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

# ─── Passo 2: Assinar o evento (XMLDSig manual — sem prefixo ds:) ────────────

def _assinar_evento(xml_evento_str: str, cert_pem: bytes, key_pem: bytes) -> str:
    """
    Assina o bloco <evento> usando RSA-SHA1 / C14N 1.0 SEM prefixo 'ds:'.

    A SEFAZ rejeita cStat 404 ("Uso de prefixo de namespace não permitido")
    quando detecta <ds:Signature>. Por isso, construímos a assinatura
    manualmente ao invés de usar signxml, garantindo que <Signature xmlns="...">
    use namespace default (sem prefixo).

    Specs SEFAZ (Evento versao 1.00):
      - Digest:           SHA-1
      - Assinatura:       RSA-SHA1
      - Canonicalização:  C14N 1.0 (sem comentários)
      - Posição:          <Signature> dentro de <evento>, após </infEvento>
    """
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_evento_str.encode("utf-8"), parser)

    inf_evento = root.find(f"{{{_NS_NFE}}}infEvento")
    id_ref = inf_evento.get("Id")

    # ── A: Digest SHA-1 do <infEvento> canonicalizado ──
    c14n_inf = etree.tostring(inf_evento, method="c14n", exclusive=False, with_comments=False)
    digest_b64 = base64.b64encode(hashlib.sha1(c14n_inf).digest()).decode()

    # ── B: Montar <SignedInfo> SEM prefixo ds: ──
    signed_info_xml = (
        f'<SignedInfo xmlns="{_NS_DSIG}">'
        f'<CanonicalizationMethod Algorithm="{_C14N_ALG}"/>'
        f'<SignatureMethod Algorithm="{_NS_DSIG}rsa-sha1"/>'
        f'<Reference URI="#{id_ref}">'
        f'<Transforms>'
        f'<Transform Algorithm="{_NS_DSIG}enveloped-signature"/>'
        f'<Transform Algorithm="{_C14N_ALG}"/>'
        f'</Transforms>'
        f'<DigestMethod Algorithm="{_NS_DSIG}sha1"/>'
        f'<DigestValue>{digest_b64}</DigestValue>'
        f'</Reference>'
        f'</SignedInfo>'
    )

    # ── C: Canonicalizar e assinar <SignedInfo> com RSA-SHA1 ──
    signed_info_el = etree.fromstring(signed_info_xml.encode("utf-8"), parser)
    c14n_si = etree.tostring(signed_info_el, method="c14n", exclusive=False, with_comments=False)

    private_key = serialization.load_pem_private_key(key_pem, password=None)
    raw_sig = private_key.sign(c14n_si, padding.PKCS1v15(), hashes.SHA1())
    sig_value_b64 = base64.b64encode(raw_sig).decode()

    # ── D: Extrair certificado X509 em DER base64 ──
    cert_obj = x509.load_pem_x509_certificate(cert_pem)
    cert_der_b64 = base64.b64encode(
        cert_obj.public_bytes(serialization.Encoding.DER)
    ).decode()

    # ── E: Montar <Signature> completa SEM prefixo ds: ──
    signature_xml = (
        f'<Signature xmlns="{_NS_DSIG}">'
        f'{signed_info_xml}'
        f'<SignatureValue>{sig_value_b64}</SignatureValue>'
        f'<KeyInfo>'
        f'<X509Data>'
        f'<X509Certificate>{cert_der_b64}</X509Certificate>'
        f'</X509Data>'
        f'</KeyInfo>'
        f'</Signature>'
    )

    # ── F: Inserir <Signature> como filha de <evento>, após </infEvento> ──
    sig_element = etree.fromstring(signature_xml.encode("utf-8"), parser)
    root.append(sig_element)

    return etree.tostring(root, encoding="unicode")


# ─── Passo 3: Montar envelope SOAP 1.2 ───────────────────────────────────────

def _montar_envelope(eventos_xml: list, id_lote: int, tp_amb: str) -> str:
    """
    Empacota até 20 <evento> assinados dentro de <envEvento> + SOAP 1.2.
    nfeDadosMsg vai direto no <Body> (sem wrapper adicional).
    """
    # CRÍTICO: NÃO usar "\n".join — whitespace pós-assinatura corrompe C14N e causa cStat 297
    eventos_concat = "".join(eventos_xml)
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

def _parsear_resposta(resp_text: str) -> tuple:
    """
    Parseia o <retEnvEvento> e retorna:
      (envelope_cStat, envelope_xMotivo, {chave: cStat})

    Se a SEFAZ rejeitar o lote inteiro (ex: cStat 215 Schema, 297 Assinatura),
    não haverá tags <retEvento> filhas — apenas o cStat do envelope.
    """
    envelope_cstat = None
    envelope_xmotivo = None
    resultado = {}
    try:
        root = etree.fromstring(resp_text.encode("utf-8"))

        # 1. Capturar cStat e xMotivo do envelope (retEnvEvento)
        ret_env = None
        for el in root.iter(f"{{{_NS_NFE}}}retEnvEvento"):
            ret_env = el
            break
        if ret_env is None:
            # Fallback: tentar sem namespace (às vezes a SEFAZ usa ns diferente)
            for el in root.iter():
                if el.tag.endswith('retEnvEvento'):
                    ret_env = el
                    break

        if ret_env is not None:
            cstat_el = ret_env.find(f"{{{_NS_NFE}}}cStat")
            xmotivo_el = ret_env.find(f"{{{_NS_NFE}}}xMotivo")
            if cstat_el is None:
                # Fallback sem namespace
                for child in ret_env:
                    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if tag == 'cStat' and cstat_el is None:
                        cstat_el = child
                    if tag == 'xMotivo' and xmotivo_el is None:
                        xmotivo_el = child
            envelope_cstat = cstat_el.text if cstat_el is not None else None
            envelope_xmotivo = xmotivo_el.text if xmotivo_el is not None else None

        # 2. Capturar resultados individuais por chave (se existirem)
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
    return envelope_cstat, envelope_xmotivo, resultado


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

    # Lê cert/key em bytes para a assinatura manual RSA-SHA1
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

            # ── Dump diagnóstico — sempre ativo ──
            _dump_diagnostico_manif(idx_lote + 1, envelope, resp.status_code, resp.text)

            env_cstat, env_xmotivo, resultado_lote = _parsear_resposta(resp.text)

            # Logar erro de envelope (lote inteiro rejeitado)
            if env_cstat and env_cstat not in ("128", "135", "136"):
                on_progresso(
                    f"[Manifestação] ⛔ SEFAZ REJEITOU O LOTE {idx_lote + 1}: "
                    f"cStat {env_cstat} — {env_xmotivo}"
                )
                on_progresso(
                    f"[Manifestação] 💡 Diagnóstico salvo em: {_DIAG_FILE_MANIF}"
                )
            else:
                on_progresso(
                    f"[Manifestação] ✅ Envelope aceito (cStat {env_cstat}). "
                    f"Processando {len(resultado_lote)} retornos individuais..."
                )

            resultado_global.update(resultado_lote)

            sucessos = sum(1 for v in resultado_lote.values() if v in ("135", "573"))
            on_progresso(
                f"[Manifestação] Lote {idx_lote + 1}: {sucessos}/{len(lote)} registrados "
                f"(135=ok, 573=duplicidade inofensiva)."
            )
        except Exception as e:
            on_progresso(f"[Manifestação] ⚠️ Erro de rede no lote {idx_lote + 1}: {e}")

    return resultado_global
