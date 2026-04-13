import pytest
import tkinter as tk
from unittest.mock import patch, MagicMock
from src.gui.app import HebronApp

@pytest.fixture
def app_instance():
    # Evitar do Tk interagir fortemente com config configs que falhariam em CI
    with patch("src.gui.app.HebronApp._build_ui"), \
         patch("src.gui.app.HebronApp._sincronizar_campos_modo"):
        
        app = HebronApp()
        # Mock manual das variaveis GUI basicas q sao usadas nos updates
        app.label_status = MagicMock()
        app.progressbar = MagicMock()
        app.btn_iniciar = MagicMock()
        return app

@patch("src.gui.app.messagebox.askyesno")
def test_alerta_saidas_popup_ok(mock_ask, app_instance):
    mock_ask.return_value = True
    eta = {'pct_saidas': 85, 'saidas': 150, 'total_horas': 2.5}
    
    ans = app_instance._alerta_saidas_popup(eta)
    assert ans is True
    
    mock_ask.assert_called_once()
    msg = mock_ask.call_args[0][1]
    assert "85%" in msg
    assert "150" in msg
    assert "2.5 hora(s)" in msg

@patch("src.gui.app.messagebox.askyesno")
def test_alerta_saidas_popup_cancel(mock_ask, app_instance):
    mock_ask.return_value = False
    ans = app_instance._alerta_saidas_popup({})
    assert ans is False

@patch("src.gui.app.iniciar_download_sefaz")
def test_task_online_calls_after(mock_iniciar, app_instance):
    """
    Checa se _task_online usa self.after e roda normalmente
    """
    app_instance.after = MagicMock()
    app_instance._task_online("ex", "pfx", "pwd", "out", "amb", "")
    
    # Callback deve registrar iniciar_download_sefaz
    mock_iniciar.assert_called_once()
    
    # E self.after foi chamado pro on_sucesso
    app_instance.after.assert_called()
