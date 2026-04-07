import os
import re
import tempfile
import datetime
import contextlib
from typing import Dict, Optional, Tuple, Any

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization

class CertificadoInvalidoError(Exception):
    pass

class CertManager:
    """Gerencia o ciclo de vida do Certificado Digital A1 (arquivo .pfx)."""

    def __init__(self, pfx_path: str, senha: str):
        if not os.path.isfile(pfx_path):
            raise CertificadoInvalidoError(f"Arquivo PFX não encontrado em: {pfx_path}")
            
        self.pfx_path = pfx_path
        
        try:
            with open(self.pfx_path, "rb") as f:
                pfx_data = f.read()
            self._private_key, self._certificate, _ = pkcs12.load_key_and_certificates(
                pfx_data, senha.encode("utf-8")
            )
        except ValueError:
            raise CertificadoInvalidoError("Senha incorreta ou formato do PFX inválido.")
        except Exception as e:
            raise CertificadoInvalidoError(f"Erro ao ler o certificado criptográfico: {str(e)}")

        self._metadados = self._extrair_metadados_certificado(self._certificate)

    def _extrair_cnpj_subject(self, subject_dict: Dict[str, str]) -> Optional[str]:
        for _, valor in subject_dict.items():
            valor_str = str(valor)
            # Tenta pegar no padrão exato final ':11111111111111'
            match_sufixo = re.search(r':(\d{14})$', valor_str)
            if match_sufixo:
                return match_sufixo.group(1)
                
            # Busca coringa
            match_direto = re.search(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b', valor_str)
            if match_direto:
                return re.sub(r'\D', '', match_direto.group())
        return None

    def _extrair_metadados_certificado(self, certificado: Any) -> Dict[str, Any]:
        subject_dict = {}
        for attr in certificado.subject:
            key = getattr(attr.oid, "_name", "OID_DESCONHECIDO")
            subject_dict[key] = str(attr.value)

        valido_de = getattr(certificado, 'not_valid_before_utc', getattr(certificado, 'not_valid_before', None))
        valido_ate = getattr(certificado, 'not_valid_after_utc', getattr(certificado, 'not_valid_after', None))

        return {
            "validade_inicial": valido_de,
            "validade_final": valido_ate,
            "cnpj_extraido": self._extrair_cnpj_subject(subject_dict)
        }

    def verificar_vigencia(self) -> bool:
        agora = datetime.datetime.now(datetime.timezone.utc)
        data_fim = self._metadados.get('validade_final')
        data_inicio = self._metadados.get('validade_inicial')
        
        if not hasattr(data_fim, 'tzinfo') or data_fim.tzinfo is None:
            agora = agora.replace(tzinfo=None)

        if data_inicio and agora < data_inicio:
            raise CertificadoInvalidoError(f"O certificado só será válido a partir de {data_inicio}")
        if data_fim and agora > data_fim:
            raise CertificadoInvalidoError(f"Certificado expirado desde {data_fim}")

        return True

    def get_cnpj(self) -> str:
        cnpj = self._metadados.get('cnpj_extraido')
        if not cnpj:
            raise CertificadoInvalidoError("O CNPJ de base não pôde ser encontrado no corpo do certificado PFX.")
        return cnpj

    @contextlib.contextmanager
    def pem_temporario(self):
        """ContextManager que gera arquivos .pem para a lib requests poder se autenticar via mTLS."""
        fd_cert, cert_path = tempfile.mkstemp(suffix=".pem")
        fd_key, key_path = tempfile.mkstemp(suffix=".pem")
        
        # Fecha os file descriptors nativos do OS para não dar leak
        os.close(fd_cert)
        os.close(fd_key)
        
        try:
            with open(cert_path, "wb") as f_cert:
                f_cert.write(self._certificate.public_bytes(serialization.Encoding.PEM))
                
            with open(key_path, "wb") as f_key:
                f_key.write(self._private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ))
                
            yield cert_path, key_path
        finally:
            if os.path.exists(cert_path):
                os.remove(cert_path)
            if os.path.exists(key_path):
                os.remove(key_path)
