import os
import json

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".HebronAutoXML")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def _load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(data: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_captcha_config() -> dict:
    """Retorna configuração de captcha guardada."""
    data = _load_config()
    return {
        "captcha_provider": data.get("captcha_provider", "2captcha"),
        "captcha_api_key": data.get("captcha_api_key", ""),
        "captcha_enabled": data.get("captcha_enabled", True)
    }

def save_captcha_config(provider: str, api_key: str, enabled: bool):
    """Salva a configuração do captcha."""
    data = _load_config()
    data["captcha_provider"] = provider
    data["captcha_api_key"] = api_key
    data["captcha_enabled"] = enabled
    _save_config(data)
