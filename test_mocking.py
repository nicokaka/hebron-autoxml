import sys
from unittest.mock import MagicMock
class MockCTkClass:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def resizable(self, *args): pass
sys.modules['tkinter'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['customtkinter'] = MagicMock()
sys.modules['customtkinter'].CTk = MockCTkClass
from src.gui.app import HebronApp
app = HebronApp()
print("Successfully instantiated HebronApp with mocked dependencies!")
