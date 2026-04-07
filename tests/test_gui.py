import unittest
import sys
from unittest.mock import MagicMock, patch

# --- MOCKING TKINTER TO ALLOW HEADLESS GUI TESTS ---
class MockCTkClass:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def resizable(self, *args): pass
    def configure(self, *args, **kwargs): pass
    
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
        
        # Interceptar chamadas agendadas (Tkinter 'after') para rodar imediatamente (Sincrono)
        self.app.after = lambda delay, callback, *args: callback(*args)
        
        # Mocks para variáveis base 
        self.app.off_excel_path = MagicMock()
        self.app.off_xml_base = MagicMock()
        self.app.off_out_path = MagicMock()
        self.app.modo_ativo = MagicMock()
        
        # Mocks dos componentes UI novos
        self.app.log_box = MagicMock()
        self.app.btn_processar = MagicMock()
        self.app.btn_abrir_pasta = MagicMock()
        self.app.seg_button = MagicMock()
        self.app.f_stats = MagicMock()
        self.app.progress_bar = MagicMock()
        self.app.lbl_pct = MagicMock()
        self.app.lbl_status = MagicMock()
        self.app.lbl_lidas = MagicMock()
        self.app.lbl_validas = MagicMock()
        self.app.lbl_baixadas = MagicMock()
        
    def test_validacao_campos_obrigatorios_offline(self):
        self.app.modo_ativo.get.return_value = "Busca Local"
        
        self.app.off_excel_path.get.return_value = ""
        self.app.off_xml_base.get.return_value = "C:/fake"
        self.app.off_out_path.get.return_value = "C:/fakeout"
        
        self.app.iniciar_roteamento()
        
        # Log box deve receber o append do erro
        self.assertTrue(self.app.log_box.insert.called)
        args, kwargs = self.app.log_box.insert.call_args
        self.assertIn("[ERRO]", args[1])
        
        # Não pode ter bloqueado UI já que não passou na validação (is_processing falso)
        self.assertFalse(self.app.is_processing)

    @patch('src.gui.app.threading.Thread')
    def test_bloqueio_interface_durante_processamento(self, mock_thread):
        self.app.modo_ativo.get.return_value = "Busca Local"
        self.app.off_excel_path.get.return_value = "C:/excel.xlsx"
        self.app.off_xml_base.get.return_value = "C:/xml_in"
        self.app.off_out_path.get.return_value = "C:/out"
        
        self.app.iniciar_roteamento()
        
        # seg_button deve ser disabled
        args, kwargs = self.app.seg_button.configure.call_args
        self.assertEqual(kwargs['state'], "disabled")
        
        # btn_processar deve ser disabled
        args, kwargs = self.app.btn_processar.configure.call_args
        self.assertEqual(kwargs['state'], "disabled")
        self.assertIn("MASTIGANDO", kwargs['text'])
        
        # A Thread pra não travar Mainloop foi ativada
        mock_thread.assert_called_once()
        instance = mock_thread.return_value
        instance.start.assert_called_once()

    @patch('src.gui.app.iniciar_extracao_hibrida')
    def test_sucesso_fluxo_callbacks_e_resumo(self, mock_core):
        mock_resultado = {
            "diretorio_saida": "C:/fake_output/Processados_123",
            "total_lidas": 10,
            "total_invalidas": 1,
            "total_duplicadas": 0,
            "total_unicas": 9,
            "total_encontradas": 9
        }
        mock_core.return_value = mock_resultado
        
        # Simulando diretamente a task interna rolando
        self.app._task_offline("ex.xlsx", "dir_in", "dir_out")
        
        # Verifica se UI reativou e populou labels de stat
        args, kwargs = self.app.btn_processar.configure.call_args
        self.assertEqual(kwargs['state'], "normal")
        
        # Verificando se inseriu stats nos labels
        self.assertTrue(self.app.lbl_lidas.configure.called)
        
        self.assertEqual(self.app.ultima_pasta_gerada, "C:/fake_output/Processados_123")
        self.assertTrue(self.app.btn_abrir_pasta.pack.called)
        self.assertTrue(self.app.f_stats.pack.called)
        
    @patch('src.gui.app.iniciar_extracao_hibrida')
    def test_falha_try_catch_trata_exception(self, mock_core):
        mock_core.side_effect = Exception("Disco Cheio")
        
        self.app._task_offline("ex.xlsx", "dir_in", "dir_out")
        
        # Verifica se a UI destravou após erro (red state progress bar)
        args_btn, kwargs_btn = self.app.btn_processar.configure.call_args
        self.assertEqual(kwargs_btn['state'], "normal")
        self.assertTrue(self.app.progress_bar.configure.called)

if __name__ == '__main__':
    unittest.main()
