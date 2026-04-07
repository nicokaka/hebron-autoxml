import sys
import traceback
from src.gui.app import HebronApp

def main():
    try:
        app = HebronApp()
        app.mainloop()
    except Exception:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Erro Fatal ao Iniciar",
            f"O programa encontrou um erro inesperado:\n\n"
            f"{traceback.format_exc()}\n\n"
            f"Por favor, envie esta mensagem ao suporte."
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
