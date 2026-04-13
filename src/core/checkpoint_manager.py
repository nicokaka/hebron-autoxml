import os
import json
import shutil
import time as _time
from datetime import datetime, timedelta
from typing import Dict, Optional

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".HebronAutoXML")
CACHE_XML_DIR = os.path.join(CACHE_DIR, "xml_cache")
_RATE_LIMIT_HOURS = 1
_CACHE_MAX_AGE_DAYS = 30


def cleanup_old_cache(max_age_days: int = _CACHE_MAX_AGE_DAYS):
    """Remove XMLs do cache local com mais de max_age_days dias."""
    if not os.path.isdir(CACHE_XML_DIR):
        return
    cutoff = _time.time() - (max_age_days * 86400)
    removed = 0
    try:
        for f in os.listdir(CACHE_XML_DIR):
            fp = os.path.join(CACHE_XML_DIR, f)
            if os.path.isfile(fp) and os.path.getmtime(fp) < cutoff:
                os.remove(fp)
                removed += 1
    except Exception:
        pass
    return removed


def _path(cnpj: str, ambiente: str) -> str:
    return os.path.join(CACHE_DIR, f"checkpoint_{cnpj}_{ambiente.lower()}.json")


def _load(cnpj: str, ambiente: str) -> dict:
    p = _path(cnpj, ambiente)
    if not os.path.exists(p):
        return {'downloaded': {}, 'blocked_at': None}
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Migração de formato antigo (lista → dicionário)
        if isinstance(data.get('downloaded'), list):
            data['downloaded'] = {k: {'arquivo': '', 'baixado_em': ''} for k in data['downloaded']}
        return data
    except Exception:
        return {'downloaded': {}, 'blocked_at': None}


def _save_data(cnpj: str, ambiente: str, data: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    data['updated_at'] = datetime.now().isoformat()
    with open(_path(cnpj, ambiente), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_downloaded(cnpj: str, ambiente: str) -> Dict[str, dict]:
    """Retorna dict de {chave: {arquivo, baixado_em}} para todas as chaves baixadas."""
    return _load(cnpj, ambiente).get('downloaded', {})


def mark_downloaded(cnpj: str, ambiente: str, chave: str, arquivo_path: str):
    """Registra uma chave como baixada com sucesso, salvando o caminho do arquivo e criando cache."""
    os.makedirs(CACHE_XML_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_XML_DIR, f"{chave}.xml")
    try:
        shutil.copy2(arquivo_path, cache_path)
    except Exception:
        pass

    data = _load(cnpj, ambiente)
    data['downloaded'][chave] = {
        'arquivo': arquivo_path,
        'cache': cache_path,
        'baixado_em': datetime.now().isoformat()
    }
    _save_data(cnpj, ambiente, data)


def mark_blocked(cnpj: str, ambiente: str):
    """Registra o timestamp de bloqueio por rate-limit (cStat 656)."""
    data = _load(cnpj, ambiente)
    data['blocked_at'] = datetime.now().isoformat()
    _save_data(cnpj, ambiente, data)


def get_cooldown_remaining(cnpj: str, ambiente: str) -> int:
    """Retorna segundos restantes do cooldown SEFAZ. 0 = livre para prosseguir."""
    blocked_at_str = _load(cnpj, ambiente).get('blocked_at')
    if not blocked_at_str:
        return 0
    try:
        blocked_at = datetime.fromisoformat(blocked_at_str)
        cooldown_end = blocked_at + timedelta(hours=_RATE_LIMIT_HOURS)
        remaining = (cooldown_end - datetime.now()).total_seconds()
        return max(0, int(remaining))
    except Exception:
        return 0


def clear_blocked(cnpj: str, ambiente: str):
    """Limpa o estado de bloqueio após o cooldown expirar."""
    data = _load(cnpj, ambiente)
    data['blocked_at'] = None
    _save_data(cnpj, ambiente, data)


def try_recover_xml(chave: str, info: dict, dest_folder: str) -> Optional[str]:
    """
    Tenta copiar o XML baixado anteriormente para a nova pasta de saída.
    Retorna o nome do arquivo se bem-sucedido, None se o arquivo original e o cache não existirem.
    """
    arquivo_original = info.get('arquivo', '')
    arquivo_cache = info.get('cache', os.path.join(CACHE_XML_DIR, f"{chave}.xml"))
    
    src_path = None
    if arquivo_original and os.path.isfile(arquivo_original):
        src_path = arquivo_original
    elif arquivo_cache and os.path.isfile(arquivo_cache):
        src_path = arquivo_cache
        
    if src_path:
        dest_name = os.path.basename(arquivo_original) if arquivo_original else f"NFe_{chave}.xml"
        if not dest_name or dest_name == ".xml":
            dest_name = f"NFe_{chave}.xml"
        dest_path = os.path.join(dest_folder, dest_name)
        try:
            shutil.copy2(src_path, dest_path)
            return dest_name
        except Exception:
            pass
    return None
