import pytest
import os
import tempfile
import cryptography.hazmat.primitives.asymmetric.rsa as rsa
import cryptography.hazmat.primitives.serialization as cert_serialization
from cryptography.hazmat.primitives import hashes
from cryptography import x509
from cryptography.x509.oid import NameOID
import datetime

# Constantes compartilhadas para testes
CHAVE_ENTRADA = "25260399999999000199550010000957721393048723"  # CNPJ emitente = 99999999000199
CHAVE_SAIDA = "25260308939548000103550010000957721393048724"    # CNPJ emitente = 08939548000103
CHAVE_FILIAL = "25260308939548000204550010000957721393048725"   # Filial (raiz 08939548)
CHAVE_CTE = "25260399999999000199570010000957721393048726"      # Modelo 57
CHAVE_NFCE = "25260399999999000199650010000957721393048727"     # Modelo 65
CNPJ_CERT = "08939548000103"


@pytest.fixture
def cert_fake_pem():
    """Gera um par de chaves e certificado dummy em PEM para testes de assinatura."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"Dummy Test Cert"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # Valid for 10 days
        datetime.datetime.utcnow() + datetime.timedelta(days=10)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
        critical=False,
    ).sign(private_key, hashes.SHA256())

    cert_pem = cert.public_bytes(cert_serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=cert_serialization.Encoding.PEM,
        format=cert_serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=cert_serialization.NoEncryption()
    )
    
    return cert_pem, key_pem


@pytest.fixture
def mock_temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d

