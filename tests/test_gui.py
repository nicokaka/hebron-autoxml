import unittest
import sys
from unittest.mock import MagicMock, patch

# --- MOCKING TKINTER TO ALLOW HEADLESS GUI TESTS ---
class MockCTkClass:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def resizable(self, *args): pass
    
mock_ctk = MagicMock()
mock_ctk.CTk = MockCTkClass
mock_tk = MagicMock()

sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['customtkinter'] = mock_ctk
# ---------------------------------------------------

from src.gui.app import HebronApp

class TestHebronAppGUI(unittest.TestCase):
    def setUp(self):
        self.app = HebronApp()
        
        # Interceptar chamadas agendadas para rodar imediatamente de forma Síncrona
        self.app._agendar_ui_update = lambda callback: callback()
        
        # Mocks para variáveis base 
        self.app.excel_path = MagicMock()
        self.app.xml_base_path = MagicMock()
        self.app.output_path = MagicMock()
        
        # Mocks dos componentes UI
        self.app.lbl_status = MagicMock()
        self.app.btn_processar = MagicMock()
        self.app.btn_abrir_pasta = MagicMock()
        
    def test_validacao_campos_obrigatorios(self):
        # Cenário de campo vazio
        self.app.excel_path.get.return_value = ""
        self.app.xml_base_path.get.return_value = "C:/fake"
        self.app.output_path.get.return_value = "C:/fakeout"
        
        self.app.iniciar_processamento()
        
        # lbl_status deve ser chamado recebendo a string de erro (vermelha)
        args, kwargs = self.app.lbl_status.configure.call_args
        self.assertIn("Preencha todos", kwargs['text'])
        self.assertEqual(kwargs['text_color'], "#ff4444")
        
        # Não pode ter bloqueado UI já que não passou na validação
        self.app.btn_processar.configure.assert_not_called()

    @patch('src.gui.app.threading.Thread')
    @patch('src.gui.app.os.path.isfile')
    @patch('src.gui.app.os.path.isdir')
    @patch('src.gui.app.os.path.exists')
    def test_bloqueio_interface_durante_processamento(self, mock_exists, mock_isdir, mock_isfile, mock_thread):
        mock_isfile.return_value = True
        mock_isdir.return_value = True
        mock_exists.return_value = True
        
        self.app.excel_path.get.return_value = "C:/excel.xlsx"
        self.app.xml_base_path.get.return_value = "C:/xml_in"
        self.app.output_path.get.return_value = "C:/out"
        
        self.app.iniciar_processamento()
        
        # btn_processar deve ser disabled
        args, kwargs = self.app.btn_processar.configure.call_args
        self.assertEqual(kwargs['state'], "disabled")
        self.assertIn("MASTIGANDO", kwargs['text'])
        
        # O botão abrir pasta deve ser escondido ao iniciar novo Job
        self.app.btn_abrir_pasta.pack_forget.assert_called_once()
        
        # A Thread pra não travar Mainloop foi ativada
        mock_thread.assert_called_once()
        instance = mock_thread.return_value
        instance.start.assert_called_once()

    @patch('src.gui.app.iniciar_extracao_hibrida')
    def test_sucesso_fluxo_callbacks_e_resumo(self, mock_core):
        # Objeto de retorno idêntico ao do core real
        mock_resultado = {
            "diretorio_saida": "C:/fake_output/Processados_123",
            "total_lidas": 10,
            "total_invalidas": 1,
            "total_duplicadas": 0,
            "total_unicas": 9,
            "total_encontradas": 9
        }
        mock_core.return_value = mock_resultado
        
        # Simulando diretamente a task interna como se fosse a Thread rolando
        self.app._task_processar()
        
        # Verifica se UI reativou e formatou texto certo
        args, kwargs = self.app.btn_processar.configure.call_args
        self.assertEqual(kwargs['state'], "normal")
        
        # O text gerado deveria citar "Lidas: 10" e "Encontradas: 9"
        args_lbl, kwargs_lbl = self.app.lbl_status.configure.call_args
        self.assertIn("Lidas: 10", kwargs_lbl['text'])
        self.assertIn("Encontradas: 9", kwargs_lbl['text'])
        self.assertEqual(kwargs_lbl['text_color'], "#00aa00")
        
        # Gravação de path
        self.assertEqual(self.app.ultima_pasta_gerada, "C:/fake_output/Processados_123")
        self.app.btn_abrir_pasta.pack.assert_called() # Botão revelado
        
    @patch('src.gui.app.iniciar_extracao_hibrida')
    def test_falha_try_catch_trata_exception(self, mock_core):
        mock_core.side_effect = Exception("Disco Cheio")
        
        self.app._task_processar()
        
        args_lbl, kwargs_lbl = self.app.lbl_status.configure.call_args
        self.assertIn("Disco Cheio", kwargs_lbl['text'])
        self.assertEqual(kwargs_lbl['text_color'], "#ff4444")
        
        args_btn, kwargs_btn = self.app.btn_processar.configure.call_args
        self.assertEqual(kwargs_btn['state'], "normal")
        self.assertIn("TENTAR DE NOVO", kwargs_btn['text'])


if __name__ == '__main__':
    unittest.main()
