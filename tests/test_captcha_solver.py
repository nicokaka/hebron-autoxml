import pytest
from unittest.mock import patch, MagicMock
from src.core.captcha_solver import CaptchaSolver, CaptchaSolverError

@patch("src.core.captcha_solver.requests.post")
@patch("src.core.captcha_solver.requests.get")
def test_2captcha_sucesso(mock_get, mock_post):
    mock_post.return_value.json.return_value = {"status": 1, "request": "TASK_123"}
    mock_get.return_value.json.side_effect = [
        {"status": 0, "request": "CAPCHA_NOT_READY"},
        {"status": 1, "request": "TOKEN_ABC"}
    ]
    
    # Reduzir sleep para testes rodarem rápido
    with patch("src.core.captcha_solver.time.sleep", return_value=None):
        solver = CaptchaSolver("minha-api", provider="2captcha")
        token = solver.resolver_hcaptcha("sitekey", "url")
        assert token == "TOKEN_ABC"

@patch("src.core.captcha_solver.requests.post")
def test_capsolver_sucesso(mock_post):
    # CapSolver usa POST para create e getTaskResult
    mock_post.side_effect = [
        MagicMock(json=lambda: {"errorId": 0, "taskId": "TASK_456"}),
        MagicMock(json=lambda: {"errorId": 0, "status": "processing"}),
        MagicMock(json=lambda: {"errorId": 0, "status": "ready", "solution": {"gRecaptchaResponse": "TOKEN_XYZ"}})
    ]
    
    with patch("src.core.captcha_solver.time.sleep", return_value=None):
        solver = CaptchaSolver("minha-api", provider="capsolver")
        token = solver.resolver_hcaptcha("sitekey", "url")
        assert token == "TOKEN_XYZ"

@patch("src.core.captcha_solver.requests.post")
def test_2captcha_erro_criacao(mock_post):
    mock_post.return_value.json.return_value = {"status": 0, "request": "ERROR_ZERO_BALANCE"}
    
    solver = CaptchaSolver("minha-api", provider="2captcha")
    with pytest.raises(CaptchaSolverError, match="ERROR_ZERO_BALANCE"):
        solver.resolver_hcaptcha("sitekey", "url")

def test_provider_invalido():
    with pytest.raises(ValueError, match="não é suportado"):
        CaptchaSolver("minha-api", provider="invalid_provider")

def test_api_key_vazia():
    with pytest.raises(ValueError, match="não configurada"):
        CaptchaSolver("")
