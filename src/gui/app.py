import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import customtkinter as ctk
import src.core.config_manager as config_mgr

from src.core.offline_job import iniciar_extracao_hibrida
from src.core.online_job import iniciar_download_sefaz
from src.__version__ import __version__

THEME = {
    "bg_primary":     "#0d1117",
    "bg_card":        "#161b22",
    "bg_input":       "#21262d",
    "border_subtle":  "#30363d",
    "accent":         "#00d4aa",
    "accent_hover":   "#00b894",
    "text_primary":   "#e6edf3",
    "text_secondary": "#8b949e",
    "text_success":   "#3fb950",
    "text_error":     "#ff6b6b",
    "font_family":    "Segoe UI",
    "font_mono":      "Consolas"
}

class HebronApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"HebronAutoXML - Processador Contábil v{__version__}")
        self.geometry("850x720")
        self.resizable(False, False)
        
        # Tema Global Base
        ctk.set_appearance_mode("Dark")
        self.configure(fg_color=THEME["bg_primary"])
        
        self.ultima_pasta_gerada = None
        self.is_processing = False
        
        # Variáveis de UI
        self.modo_ativo = ctk.StringVar(value="Download SEFAZ")
        self.on_excel_path = tk.StringVar()
        self.on_pfx_path = tk.StringVar()
        self.on_senha = tk.StringVar()
        self.on_out_path = tk.StringVar()
        
        cfg = config_mgr.get_captcha_config()
        self.on_captcha_api_key = ctk.StringVar(value=cfg["captcha_api_key"])
        
        self.off_xml_base = tk.StringVar()

        self._build_ui()
        self._sincronizar_campos_modo(self.modo_ativo.get())
        
    def _build_ui(self):
        self._build_zona_header()
        self._build_zona_switcher()
        self._build_zona_form()
        self._build_zona_progress()
        self._build_zona_action()
        
        # Rodapé de Versão
        ctk.CTkLabel(
            self.frm_card,
            text=f"v{__version__} • Hebron Contabilidade",
            font=ctk.CTkFont(size=11),
            text_color=THEME["text_secondary"]
        ).pack(side="bottom", pady=(0, 8))
        
    def _build_zona_header(self):
        f = ctk.CTkFrame(self, fg_color=THEME["bg_primary"])
        f.pack(fill="x", padx=40, pady=(25, 10))
        
        lbl_icon = ctk.CTkLabel(f, text="🛡️", font=ctk.CTkFont(size=36))
        lbl_icon.pack(side="left")
        
        lbl_title = ctk.CTkLabel(
            f, text=" HebronAutoXML", 
            font=ctk.CTkFont(family=THEME["font_family"], size=28, weight="bold"),
            text_color=THEME["text_primary"]
        )
        lbl_title.pack(side="left", anchor="s", pady=(0, 5))
        
        lbl_sub = ctk.CTkLabel(
            f, text=f" v{__version__} — Processador Contábil", 
            font=ctk.CTkFont(family=THEME["font_family"], size=14),
            text_color=THEME["text_secondary"]
        )
        lbl_sub.pack(side="left", anchor="s", padx=10, pady=(0, 8))

    def _build_zona_switcher(self):
        self.seg_button = ctk.CTkSegmentedButton(
            self,
            values=["Download SEFAZ", "Busca Local"],
            variable=self.modo_ativo,
            command=self._sincronizar_campos_modo,
            font=ctk.CTkFont(weight="bold"),
            selected_color=THEME["accent"],
            selected_hover_color=THEME["accent_hover"],
            unselected_color=THEME["bg_primary"],
            unselected_hover_color=THEME["bg_card"],
            text_color=THEME["text_primary"]
        )
        self.seg_button.pack(fill="x", padx=40, pady=(10, 20))

    def _build_zona_form(self):
        self.frm_card = ctk.CTkFrame(self, fg_color=THEME["bg_card"], border_width=1, border_color=THEME["border_subtle"], corner_radius=8)
        self.frm_card.pack(fill="x", padx=40)
        
        self.row_excel = self._criar_input_row("📊 Planilha de Chaves", self.on_excel_path, self._cmd_buscar_excel)
        self.row_pfx = self._criar_input_row("🔐 Certificado (.pfx)", self.on_pfx_path, self._cmd_buscar_pfx)
        self.row_xml = self._criar_input_row("📁 Pasta Local (XMLs)", self.off_xml_base, self._cmd_buscar_xml_base)
        
        # Row Especial para Senha e Captcha API
        self.row_senha = ctk.CTkFrame(self.frm_card, fg_color=THEME["bg_card"])
        self.row_senha.pack(fill="x", padx=20, pady=10)
        
        # Senha
        ctk.CTkLabel(self.row_senha, text="🔑 Senha", width=70, anchor="w", font=ctk.CTkFont(weight="bold"), text_color=THEME["text_primary"]).pack(side="left")
        ctk.CTkEntry(self.row_senha, textvariable=self.on_senha, show="•", fg_color=THEME["bg_input"], border_width=1, width=120).pack(side="left", padx=(0, 20))
        
        # API Key Captcha
        ctk.CTkLabel(self.row_senha, text="🛡️ 2Captcha/CapSolver API Key (Opcional):", anchor="w", text_color=THEME["text_secondary"], font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkEntry(self.row_senha, textvariable=self.on_captcha_api_key, fg_color=THEME["bg_input"], border_width=1, show="*", width=200).pack(side="left", padx=(5, 0))
        
        self.row_out = self._criar_input_row("📦 Pasta de Saída", self.on_out_path, self._cmd_buscar_out)

    def _criar_input_row(self, label_text, str_var, cmd):
        row = ctk.CTkFrame(self.frm_card, fg_color=THEME["bg_card"])
        row.pack(fill="x", padx=20, pady=10)
        
        lbl = ctk.CTkLabel(row, text=label_text, width=180, anchor="w", font=ctk.CTkFont(weight="bold"), text_color=THEME["text_primary"])
        lbl.pack(side="left")
        
        entry = ctk.CTkEntry(row, textvariable=str_var, fg_color=THEME["bg_input"], border_width=1, border_color=THEME["border_subtle"])
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn = ctk.CTkButton(row, text="Procurar...", width=90, fg_color=THEME["bg_card"], border_width=1, border_color=THEME["border_subtle"], text_color=THEME["text_primary"], hover_color=THEME["bg_input"], command=cmd)
        btn.pack(side="right")
        return row

    def _build_zona_progress(self):
        f = ctk.CTkFrame(self, fg_color=THEME["bg_primary"])
        f.pack(fill="both", expand=True, padx=40, pady=(20, 10))
        
        # Barra e textos
        f_top = ctk.CTkFrame(f, fg_color=THEME["bg_primary"])
        f_top.pack(fill="x", pady=(0, 5))
        self.lbl_pct = ctk.CTkLabel(f_top, text="0%", text_color=THEME["accent"], font=ctk.CTkFont(weight="bold"))
        self.lbl_pct.pack(side="left")
        self.lbl_status = ctk.CTkLabel(f_top, text="Aguardando início...", text_color=THEME["text_secondary"])
        self.lbl_status.pack(side="right")
        
        self.progress_bar = ctk.CTkProgressBar(f, progress_color=THEME["accent"], fg_color=THEME["bg_input"], height=10)
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.set(0)
        
        self.log_box = ctk.CTkTextbox(f, height=120, state="disabled", fg_color=THEME["bg_card"], border_width=1, border_color=THEME["border_subtle"], text_color=THEME["accent"], font=ctk.CTkFont(family=THEME["font_mono"]))
        self.log_box.pack(fill="both", expand=True)

    def _build_zona_action(self):
        f = ctk.CTkFrame(self, fg_color=THEME["bg_primary"])
        f.pack(fill="x", padx=40, pady=(0, 25))
        
        self.btn_processar = ctk.CTkButton(
            f, text="INICIAR DOWNLOAD", font=ctk.CTkFont(weight="bold", size=15), height=45, 
            fg_color=THEME["accent"], hover_color=THEME["accent_hover"], text_color="#000000",
            command=self.iniciar_roteamento
        )
        self.btn_processar.pack(fill="x", pady=(0, 15))
        
        # Stats
        self.f_stats = ctk.CTkFrame(f, fg_color=THEME["bg_primary"])
        # Será empacotado durante/depois processamento
        
        box_lidas, self.lbl_lidas = self._criar_stat_box("Lidas", "0")
        box_lidas.pack(side="left", expand=True, padx=5)
        
        box_validas, self.lbl_validas = self._criar_stat_box("Válidas", "0", THEME["text_success"])
        box_validas.pack(side="left", expand=True, padx=5)
        
        box_baixadas, self.lbl_baixadas = self._criar_stat_box("Resultados", "0", THEME["accent"])
        box_baixadas.pack(side="left", expand=True, padx=5)
        
        self.btn_abrir_pasta = ctk.CTkButton(f, text="Abrir Pasta de Saída", fg_color=THEME["bg_primary"], hover_color=THEME["bg_input"], border_width=1, border_color=THEME["border_subtle"], text_color=THEME["text_primary"], command=self._cmd_abrir_pasta)

    def _criar_stat_box(self, titulo, valor, cor_valor=None):
        box = ctk.CTkFrame(self.f_stats, fg_color=THEME["bg_card"], border_width=1, border_color=THEME["border_subtle"])
        ctk.CTkLabel(box, text=titulo, text_color=THEME["text_secondary"], font=ctk.CTkFont(size=11)).pack(pady=(5, 0))
        lbl_v = ctk.CTkLabel(box, text=valor, text_color=cor_valor or THEME["text_primary"], font=ctk.CTkFont(weight="bold", size=16))
        lbl_v.pack(pady=(0, 5))
        return box, lbl_v

    # --- LÓGICA DE UI E CALLBACKS ---
    def _sincronizar_campos_modo(self, modo):
        self.row_pfx.pack_forget()
        self.row_senha.pack_forget()
        self.row_xml.pack_forget()

        if modo == "Download SEFAZ":
            self.row_senha.pack(fill="x", padx=20, pady=10, before=self.row_out)
            self.row_pfx.pack(fill="x", padx=20, pady=10, before=self.row_senha)
            self.btn_processar.configure(text="INICIAR DOWNLOAD")
        else:
            self.row_xml.pack(fill="x", padx=20, pady=10, before=self.row_out)
            self.btn_processar.configure(text="INICIAR BUSCA LOCAL")

    def _cmd_buscar_excel(self):
        p = filedialog.askopenfilename(filetypes=[("Planilhas", "*.xlsx")])
        if p:
            self.on_excel_path.set(p)
            
    def _cmd_buscar_pfx(self):
        p = filedialog.askopenfilename(filetypes=[("Certificado", "*.pfx"), ("Todos", "*.*")])
        if p: self.on_pfx_path.set(p)

    def _cmd_buscar_xml_base(self):
        p = filedialog.askdirectory()
        if p: self.off_xml_base.set(p)
        
    def _cmd_buscar_out(self):
        p = filedialog.askdirectory()
        if p:
            self.on_out_path.set(p)

    def _log(self, message):
        timestamp = os.environ.get("MOCK_TIMESTAMP", datetime.now().strftime("%H:%M:%S"))
        linha = f"[{timestamp}] {message}"
        
        self.log_box.configure(state="normal")
        self.log_box.insert("end", linha + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _atualizar_progresso(self, msg, atual=None, total=None):
        self._log(msg)
        if atual is not None and total is not None and total > 0:
            pct = atual / total
            self.progress_bar.set(pct)
            self.lbl_pct.configure(text=f"{int(pct*100)}%")
            self.lbl_status.configure(text=f"Processando {atual} de {total}...")
        elif msg == "Concluído":
            self.progress_bar.set(1.0)
            self.lbl_pct.configure(text="100%")
            self.lbl_status.configure(text="Finalizado.")

    def iniciar_roteamento(self):
        if self.is_processing: return
        self.btn_abrir_pasta.pack_forget()
        self.f_stats.pack_forget()
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.progress_bar.configure(progress_color=THEME["accent"])
        self.progress_bar.set(0)
        self.lbl_pct.configure(text="0%")
        
        if self.modo_ativo.get() == "Download SEFAZ":
            self._disparar_online()
        else:
            self._disparar_offline()

    def _travar_ui(self):
        self.is_processing = True
        self.seg_button.configure(state="disabled")
        self.btn_processar.configure(state="disabled", text="MASTIGANDO... AGUARDE")
        
    def _destravar_ui(self):
        self.is_processing = False
        self.seg_button.configure(state="normal")
        self.btn_processar.configure(state="normal", text="INICIAR PROCESSO NOVAMENTE")
        self.f_stats.pack(fill="x", pady=(0, 10))

    def _disparar_online(self):
        ex = self.on_excel_path.get()
        pfx = self.on_pfx_path.get()
        pwd = self.on_senha.get()
        out = self.on_out_path.get()
        amb = "producao" # Travado FSist
        api_key = self.on_captcha_api_key.get().strip()
        
        if api_key:
            # Detecta provedor pela estrutura simples da key (ajuste como achar melhor ou trave em 2captcha)
            prov = "capsolver" if api_key.startswith("CAP-") else "2captcha"
            config_mgr.save_captcha_config(prov, api_key, True)
        else:
            config_mgr.save_captcha_config("2captcha", "", False)
        
        if not all([ex, pfx, pwd, out]):
            self._log("[ERRO] Preencha: Excel, Certificado PFX, Senha e Pasta de Saída.")
            return
            
        self._travar_ui()
        self._log("Iniciando Módulo SEFAZ Online...")
        
        t = threading.Thread(target=self._task_online, args=(ex, pfx, pwd, out, amb, api_key))
        t.daemon = True
        t.start()

    def _disparar_offline(self):
        ex = self.on_excel_path.get()
        base = self.off_xml_base.get()
        out = self.on_out_path.get()
        
        if not all([ex, base, out]):
            self._log("[ERRO] Preencha: Excel, Pasta Secundária e Pasta de Saída.")
            return

        self._travar_ui()
        self._log("Iniciando varredura Offline Local...")
        
        t = threading.Thread(target=self._task_offline, args=(ex, base, out))
        t.daemon = True
        t.start()

    def _alerta_saidas_popup(self, eta: dict) -> bool:
        """Exibe popup de alerta vermelho quando >80% das chaves são saídas.
        Retorna True para continuar, False para cancelar."""
        horas = eta.get('total_horas', '?')
        total = eta.get('saidas', '?')
        pct = eta.get('pct_saidas', '?')
        mensagem = (
            f"⚠️ ALERTA: {pct}% das notas inseridas ({total}) foram emitidas "
            f"pelo próprio cliente (Saídas).\n\n"
            f"O Governo Federal restringe o download destas notas,\n"
            f"liberando apenas 20 por hora.\n\n"
            f"⏱️ Tempo estimado de conclusão: {horas} hora(s).\n"
            f"O computador precisará ficar LIGADO durante todo o processo.\n\n"
            f"Deseja continuar mesmo assim?"
        )
        resultado = messagebox.askyesno(
            "⚠️ Atenção — Download Demorado",
            mensagem,
            icon='warning'
        )
        return resultado

    def _task_online(self, ex, pfx, pwd, out, amb, api_key):
        try:
            cb = lambda m, a=None, t=None: self.after(0, self._atualizar_progresso, m, a, t)
            # on_alerta_saidas roda na main thread via after() para poder abrir MessageBox
            alerta_resultado = [True]  # default: continuar
            def alerta_cb(eta):
                import threading as _th
                ev = _th.Event()
                def _popup():
                    alerta_resultado[0] = self._alerta_saidas_popup(eta)
                    ev.set()
                self.after(0, _popup)
                ev.wait(timeout=120)  # aguarda resposta do usuário por até 2 min
                return alerta_resultado[0]

            res = iniciar_download_sefaz(ex, pfx, pwd, out, amb, on_progresso=cb, on_alerta_saidas=alerta_cb, captcha_api_key=api_key)
            self.after(0, self._on_sucesso, res)
        except Exception as e:
            self.after(0, self._on_erro, str(e))

    def _task_offline(self, ex, base, out):
        try:
            cb = lambda m, a=None, t=None: self.after(0, self._atualizar_progresso, m, a, t)
            res = iniciar_extracao_hibrida(ex, base, out, on_progresso=cb)
            self.after(0, self._on_sucesso, res)
        except Exception as e:
            self.after(0, self._on_erro, str(e))

    def _on_sucesso(self, res: dict):
        self._destravar_ui()
        self.ultima_pasta_gerada = res.get('diretorio_saida')
        
        self.lbl_lidas.configure(text=str(res.get('total_lidas', 0)))
        self.lbl_validas.configure(text=str(res.get('total_unicas', 0)))
        self.lbl_baixadas.configure(text=str(res.get('total_encontradas', 0)))
        
        self.btn_abrir_pasta.pack(pady=(10, 0))
        messagebox.showinfo("Sucesso", "Trabalho Concluído! Verifique a pasta de processados.")

    def _on_erro(self, msg_erro: str):
        self._destravar_ui()
        self.progress_bar.configure(progress_color=THEME["text_error"])
        self._log(f"[FALHA FATAL] {msg_erro}")
        messagebox.showerror("Erro de Execução", "Falha crítica. Verifique os logs.")

    def _cmd_abrir_pasta(self):
        if self.ultima_pasta_gerada and os.path.isdir(self.ultima_pasta_gerada):
            import subprocess, sys
            if sys.platform == "win32":
                os.startfile(self.ultima_pasta_gerada)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.ultima_pasta_gerada])
            else:
                subprocess.Popen(["xdg-open", self.ultima_pasta_gerada])

if __name__ == "__main__":
    app = HebronApp()
    app.mainloop()
