import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.core.offline_job import iniciar_extracao_hibrida

class HebronApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("HebronAutoXML - Processador Contábil")
        self.geometry("750x550")
        self.resizable(False, False)
        
        # Tema padrão limpo e sério
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        # Variáveis de Caminhos
        self.excel_path = tk.StringVar()
        self.xml_base_path = tk.StringVar()
        self.output_path = tk.StringVar()
        
        self.ultima_pasta_gerada = None
        
        self.build_ui()
        
    def build_ui(self):
        # Título Master
        header = ctk.CTkLabel(self, text="Sistema de Validação e Limpeza de XMLs", font=ctk.CTkFont(size=20, weight="bold"))
        header.pack(pady=(20, 30))
        
        # Frame Inputs
        frame_inputs = ctk.CTkFrame(self, fg_color="transparent")
        frame_inputs.pack(fill="x", padx=40)
        
        # --- input excel
        lbl_excel = ctk.CTkLabel(frame_inputs, text="Planilha de Chaves (Excel):", font=ctk.CTkFont(weight="bold"))
        lbl_excel.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        row_excel = ctk.CTkFrame(frame_inputs, fg_color="transparent")
        row_excel.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        row_excel.columnconfigure(0, weight=1)
        
        entry_excel = ctk.CTkEntry(row_excel, textvariable=self.excel_path, state="disabled", width=450)
        entry_excel.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        btn_excel = ctk.CTkButton(row_excel, text="Procurar...", width=100, command=self.buscar_excel)
        btn_excel.grid(row=0, column=1)

        # --- input pasta XMLs
        lbl_xml = ctk.CTkLabel(frame_inputs, text="Pasta de XMLs Base (Raiz Sefaz Fixa):", font=ctk.CTkFont(weight="bold"))
        lbl_xml.grid(row=2, column=0, sticky="w", pady=(0, 5))
        
        row_xml = ctk.CTkFrame(frame_inputs, fg_color="transparent")
        row_xml.grid(row=3, column=0, sticky="ew", pady=(0, 15))
        row_xml.columnconfigure(0, weight=1)
        
        entry_xml = ctk.CTkEntry(row_xml, textvariable=self.xml_base_path, state="disabled", width=450)
        entry_xml.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        btn_xml = ctk.CTkButton(row_xml, text="Procurar...", width=100, command=self.buscar_pasta_xml)
        btn_xml.grid(row=0, column=1)
        
        # --- input pasta Saida
        lbl_out = ctk.CTkLabel(frame_inputs, text="Pasta de Saída (Onde jogar Resultados):", font=ctk.CTkFont(weight="bold"))
        lbl_out.grid(row=4, column=0, sticky="w", pady=(0, 5))
        
        row_out = ctk.CTkFrame(frame_inputs, fg_color="transparent")
        row_out.grid(row=5, column=0, sticky="ew", pady=(0, 15))
        row_out.columnconfigure(0, weight=1)
        
        entry_out = ctk.CTkEntry(row_out, textvariable=self.output_path, state="disabled", width=450)
        entry_out.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        btn_out = ctk.CTkButton(row_out, text="Procurar...", width=100, command=self.buscar_pasta_saida)
        btn_out.grid(row=0, column=1)
        
        
        # Action Buttons Area
        self.frame_actions = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_actions.pack(fill="x", padx=40, pady=(20, 10))
        
        self.btn_processar = ctk.CTkButton(self.frame_actions, text="PROCESSAR", font=ctk.CTkFont(weight="bold", size=15), height=45, fg_color="#228b22", hover_color="#006400", command=self.iniciar_processamento)
        self.btn_processar.pack(fill="x")
        
        # Area de Status
        self.lbl_status = ctk.CTkLabel(self, text="Aguardando seleção de arquivos...", text_color="gray")
        self.lbl_status.pack(pady=(10, 5))
        
        self.btn_abrir_pasta = ctk.CTkButton(self, text="Abrir Pasta Gerada", fg_color="gray", command=self.abrir_pasta_saida)
        # Oculto até que haja sucesso. Será renderizado no pack pós sucesso
        
    def buscar_excel(self):
        pth = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if pth:
            self.excel_path.set(pth)
            
    def buscar_pasta_xml(self):
        pth = filedialog.askdirectory(title="Selecione a Pasta Contendo os XMLs")
        if pth:
            self.xml_base_path.set(pth)
            
    def buscar_pasta_saida(self):
        pth = filedialog.askdirectory(title="Selecione a Pasta de Saída dos Relatórios")
        if pth:
            self.output_path.set(pth)
            
    def iniciar_processamento(self):
        # Validações primárias
        if not self.excel_path.get() or not self.xml_base_path.get() or not self.output_path.get():
            self.lbl_status.configure(text="STATUS: Preencha todos os três diretórios antes de continuar.", text_color="#ff4444")
            return
            
        # Oculta botão de pasta anterior caso estivesse visível
        self.btn_abrir_pasta.pack_forget()
        
        # Trava UI
        self.btn_processar.configure(state="disabled", text="MASTIGANDO... AGUARDE")
        self.lbl_status.configure(text="STATUS: Fazendo Parsing e Varrendo a Nuvem Local... O tempo depende dos XMLs.", text_color="#ffd700")
        
        # Levanta Thread limpa
        t = threading.Thread(target=self._task_processar)
        t.daemon = True
        t.start()
        
    def _task_processar(self):
        try:
            resultado = iniciar_extracao_hibrida(
                self.excel_path.get(),
                self.xml_base_path.get(),
                self.output_path.get()
            )
            self._on_sucesso(resultado)
            
        except Exception as e:
            self._on_erro(str(e))
            
    def _on_sucesso(self, res: dict):
        # Transição de Thread segurda pro Tkinter
        self.ultima_pasta_gerada = res['diretorio_saida']
        
        faltantes = res['total_unicas'] - res['total_encontradas']
        
        msg_resumo = (
            f"Concluído com Sucesso!\n"
            f"Lidas: {res['total_lidas']} | Inválidas: {res['total_invalidas']} | Duplicadas: {res['total_duplicadas']}\n"
            f"--- BATERIA DE MATCH ---\n"
            f"Buscadas: {res['total_unicas']} | Encontradas: {res['total_encontradas']} | Faltantes: {faltantes}"
        )
        
        def ui_update():
            self.lbl_status.configure(text=msg_resumo, text_color="#00aa00")
            self.btn_processar.configure(state="normal", text="PROCESSAR NOVAMENTE")
            self.btn_abrir_pasta.pack(pady=(10, 0))
            # Mostra o Popup simples estipulado
            messagebox.showinfo("Sucesso", "Pipeline finalizado! O ZIP e a Planilha nova já foram soltos na pasta.")
            
        self.after(0, ui_update)
        
    def _on_erro(self, msg_erro: str):
        def ui_update():
            self.lbl_status.configure(text=f"STATUS: ERRO FATAL - {msg_erro}", text_color="#ff4444")
            self.btn_processar.configure(state="normal", text="TENTAR DE NOVO")
            
        self.after(0, ui_update)

    def abrir_pasta_saida(self):
        if self.ultima_pasta_gerada and os.path.isdir(self.ultima_pasta_gerada):
            import subprocess
            import sys
            
            # Cross-OS open command nativo nativo puro fallback
            if sys.platform == "win32":
                os.startfile(self.ultima_pasta_gerada)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.ultima_pasta_gerada])
            else:
                subprocess.Popen(["xdg-open", self.ultima_pasta_gerada])
