import os
import json
from datetime import datetime
from typing import Dict, Any

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".HebronAutoXML")
CACHE_FILE = os.path.join(CACHE_DIR, "nsu_cache.json")

def _load_cache() -> Dict[str, Any]:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(data: Dict[str, Any]):
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def get_cached_nsu(cnpj: str, ambiente: str) -> str:
    """Retorna o ultNSU salvo para o CNPJ e ambiente, ou '0' se não houver."""
    cache = _load_cache()
    amb = ambiente.lower()
    if cnpj in cache and amb in cache[cnpj]:
        return cache[cnpj][amb].get("ultNSU", "0")
    return "0"

def save_nsu(cnpj: str, ambiente: str, ult_nsu: str):
    """Salva o ultNSU retornado pela Sefaz de forma persistente."""
    cache = _load_cache()
    amb = ambiente.lower()
    
    if cnpj not in cache:
        cache[cnpj] = {}
        
    cache[cnpj][amb] = {
        "ultNSU": str(ult_nsu),
        "updated_at": datetime.now().isoformat()
    }
    _save_cache(cache)
