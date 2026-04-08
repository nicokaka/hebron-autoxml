import pytest
import os
import json
from unittest.mock import patch
from datetime import datetime, timedelta
import src.core.checkpoint_manager as cp

@pytest.fixture
def setup_checkpoint(mock_temp_dir):
    with patch("src.core.checkpoint_manager.CACHE_DIR", mock_temp_dir):
        yield mock_temp_dir

def test_mark_and_get_downloaded(setup_checkpoint):
    cp.mark_downloaded("12345678901234", "producao", "CHAVE_TESTE_1", "/path/to/file.xml")
    downloaded = cp.get_downloaded("12345678901234", "producao")
    
    assert "CHAVE_TESTE_1" in downloaded
    assert downloaded["CHAVE_TESTE_1"]["arquivo"] == "/path/to/file.xml"
    assert "baixado_em" in downloaded["CHAVE_TESTE_1"]

def test_migracao_formato_antigo(setup_checkpoint):
    # Simula um JSON antigo onde 'downloaded' era lista
    p = cp._path("12345678901234", "producao")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"downloaded": ["CHAVE_VELHA"]}, f)

    downloaded = cp.get_downloaded("12345678901234", "producao")
    assert "CHAVE_VELHA" in downloaded
    assert isinstance(downloaded["CHAVE_VELHA"], dict)
    assert downloaded["CHAVE_VELHA"]["arquivo"] == ""

def test_cooldown_mark_and_get(setup_checkpoint):
    cp.mark_blocked("123", "homologacao")
    remaining = cp.get_cooldown_remaining("123", "homologacao")
    assert remaining > 0
    assert remaining <= 3600  # 1 hora max

def test_cooldown_expired(setup_checkpoint):
    # Simular bloqueio que aconteceu há 2 horas
    data = cp._load("123", "homologacao")
    data["blocked_at"] = (datetime.now() - timedelta(hours=2)).isoformat()
    cp._save_data("123", "homologacao", data)
    
    remaining = cp.get_cooldown_remaining("123", "homologacao")
    assert remaining == 0

def test_clear_blocked(setup_checkpoint):
    cp.mark_blocked("123", "homologacao")
    cp.clear_blocked("123", "homologacao")
    remaining = cp.get_cooldown_remaining("123", "homologacao")
    assert remaining == 0

def test_try_recover_xml(setup_checkpoint):
    # Criar um arquivo fake para recuperar
    original_path = os.path.join(setup_checkpoint, "xml_original.xml")
    with open(original_path, "w") as f:
        f.write("<fake></fake>")
    
    nova_pasta = os.path.join(setup_checkpoint, "nova_pasta")
    os.makedirs(nova_pasta, exist_ok=True)
    
    rec_filename = cp.try_recover_xml("CHAVE1", {"arquivo": original_path}, nova_pasta)
    assert rec_filename == "xml_original.xml"
    assert os.path.exists(os.path.join(nova_pasta, "xml_original.xml"))

def test_try_recover_xml_missing(setup_checkpoint):
    rec_filename = cp.try_recover_xml("CHAVE1", {"arquivo": "/path/missing.xml"}, setup_checkpoint)
    assert rec_filename is None
