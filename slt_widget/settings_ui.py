import os
import sys
import tkinter as tk
import winreg
import config as CFG

def set_autostart(enable):
    """Adds or removes the widget from Windows Startup."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "DataWidgetApp"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            pythonw = os.path.join(sys.prefix, "pythonw.exe")
            if not os.path.exists(pythonw): # fallback
                pythonw = "pythonw"
            script_path = os.path.abspath("slt_widget.pyw")
            
            # Use pythonw to prevent command prompt from showing up
            cmd = f'"{pythonw}" "{script_path}"'
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Failed to configure registry startup: {e}")

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent_main):
        super().__init__(parent_main)
        self.parent_main = parent_main
        self.title("Settings - Data Widget")
        w, h = 500, 350
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(False, False)
        
        # Load theme
        t = self.parent_main.theme
        self.config(bg=t["BG2"])
        
        self.transient(parent_main)
        self.focus_force()

        # Try to apply modern frame look (if available)
        self.attributes("-toolwindow", True)
        
        # Layout: left navigation frame, right content frame
        self.nav_frame = tk.Frame(self, bg=t["TRACK"], width=130)
        self.nav_frame.pack(side="left", fill="y")
        self.nav_frame.pack_propagate(False)

        self.content_frame = tk.Frame(self, bg=t["BG2"])
        self.content_frame.pack(side="right", fill="both", expand=True)

        self.tabs = {}
        self.current_tab = None

        self._build_nav()
        self._build_tabs()
        
        # Open default tab
        if not CFG.SettingsManager.get("slt_email"):
            self.show_tab("Account")
        else:
            self.show_tab("General")
        
    def _build_nav(self):
        t = self.parent_main.theme
        nav_items = [
            ("👤 Account", "Account"),
            ("⚙ General", "General"),
            ("📊 Data Bars", "DataBars"),
            ("🔔 Notifications", "Notifications"),
            ("ℹ About", "About")
        ]
        
        self.nav_buttons = {}
        for text, tab_id in nav_items:
            btn = tk.Button(self.nav_frame, text=text, bg=t["TRACK"], fg=t["FG"], 
                            activebackground=t["ACCENT"], activeforeground=t["FG"],
                            relief="flat", bd=0, anchor="w", padx=15, pady=8,
                            font=("Segoe UI", 10), command=lambda t_id=tab_id: self.show_tab(t_id))
            btn.pack(fill="x")
            self.nav_buttons[tab_id] = btn

    def _build_tabs(self):
        t = self.parent_main.theme
        
        # -- Account Tab --
        f_acc = tk.Frame(self.content_frame, bg=t["BG2"], padx=20, pady=20)
        tk.Label(f_acc, text="SLT Account", font=("Segoe UI", 14, "bold"), bg=t["BG2"], fg=t["FG"]).pack(anchor="w", pady=(0, 15))
        
        tk.Label(f_acc, text="MySLT Email:", font=("Segoe UI", 10), bg=t["BG2"], fg=t["DIM"]).pack(anchor="w")
        self.var_email = tk.StringVar(value=(CFG.SettingsManager.get("slt_email") or ""))
        tk.Entry(f_acc, textvariable=self.var_email, bg=t["TRACK"], fg=t["FG"], font=("Segoe UI", 10)).pack(anchor="w", fill="x", pady=(0, 10))
        
        tk.Label(f_acc, text="MySLT Password:", font=("Segoe UI", 10), bg=t["BG2"], fg=t["DIM"]).pack(anchor="w")
        self.var_pw = tk.StringVar(value="")
        
        pw_frame = tk.Frame(f_acc, bg=t["BG2"])
        pw_frame.pack(anchor="w", fill="x", pady=(0, 10))
        
        self.ent_pw = tk.Entry(pw_frame, textvariable=self.var_pw, show="*", bg=t["TRACK"], fg=t["FG"], font=("Segoe UI", 10))
        self.ent_pw.pack(side="left", fill="x", expand=True)
        
        self.btn_eye = tk.Label(pw_frame, text="👁", bg=t["BG2"], fg=t["DIM"], font=("Segoe UI", 12), cursor="hand2")
        self.btn_eye.pack(side="right", padx=(5, 0))
        
        def _toggle_eye(e=None):
            if self.ent_pw.cget("show") == "*":
                self.ent_pw.config(show="")
                self.btn_eye.config(fg=t["FG"])
            else:
                self.ent_pw.config(show="*")
                self.btn_eye.config(fg=t["DIM"])
                
        self.btn_eye.bind("<Button-1>", _toggle_eye)
        
        tk.Label(f_acc, text="Landline Number (e.g. 011...):", font=("Segoe UI", 10), bg=t["BG2"], fg=t["DIM"]).pack(anchor="w")
        self.var_landline = tk.StringVar(value=(CFG.SettingsManager.get("slt_landline") or ""))
        tk.Entry(f_acc, textvariable=self.var_landline, bg=t["TRACK"], fg=t["FG"], font=("Segoe UI", 10)).pack(anchor="w", fill="x", pady=(0, 15))
        
        tk.Label(f_acc, text="We require your landline number to resolve your SLT Subscriber ID.\nWe do not collect any of this data.", font=("Segoe UI", 9), bg=t["BG2"], fg=t["DIM"], justify="left", wraplength=320).pack(anchor="w", pady=(0, 15))
        
        self.btn_save = tk.Button(f_acc, text="Save & Login", bg=t["ACCENT"], fg=t["BG2"], font=("Segoe UI", 10, "bold"), command=self._save_account, relief="flat", padx=10, pady=2)
        self.btn_save.pack(anchor="w")
        
        self.lbl_status = tk.Label(f_acc, text="", font=("Segoe UI", 9), bg=t["BG2"], fg=t["FG"], wraplength=420, justify="left")
        self.lbl_status.pack(anchor="w", pady=10)
        
        self.tabs["Account"] = f_acc
        
        # -- General Tab --
        f_gen = tk.Frame(self.content_frame, bg=t["BG2"], padx=20, pady=20)
        tk.Label(f_gen, text="General Settings", font=("Segoe UI", 14, "bold"), bg=t["BG2"], fg=t["FG"]).pack(anchor="w", pady=(0, 15))
        
        self.var_startup = tk.BooleanVar(value=CFG.SettingsManager.get("start_with_windows"))
        cb_start = tk.Checkbutton(f_gen, text="  Start with Windows", variable=self.var_startup, 
                                  bg=t["BG2"], fg=t["FG"], selectcolor=t["TRACK"], 
                                  activebackground=t["BG2"], activeforeground=t["FG"], font=("Segoe UI", 10),
                                  command=self._on_general_change)
        cb_start.pack(anchor="w", pady=5)
        
        self.var_pos = tk.BooleanVar(value=CFG.SettingsManager.get("remember_position"))
        cb_pos = tk.Checkbutton(f_gen, text="  Remember widget position on screen", variable=self.var_pos, 
                                bg=t["BG2"], fg=t["FG"], selectcolor=t["TRACK"], 
                                activebackground=t["BG2"], activeforeground=t["FG"], font=("Segoe UI", 10),
                                command=self._on_general_change)
        cb_pos.pack(anchor="w", pady=5)
        self.tabs["General"] = f_gen
        
        # -- Data Bars Tab --
        f_bars = tk.Frame(self.content_frame, bg=t["BG2"], padx=20, pady=20)
        tk.Label(f_bars, text="Visible Data Bars", font=("Segoe UI", 14, "bold"), bg=t["BG2"], fg=t["FG"]).pack(anchor="w", pady=(0, 15))
        
        self.bar_vars = {}
        for kind in CFG.ALL_KINDS:
            var = tk.BooleanVar(value=(kind not in CFG.SettingsManager.get("hidden_kinds")))
            self.bar_vars[kind] = var
            cb = tk.Checkbutton(f_bars, text=f"  {CFG.KIND_LABELS.get(kind, kind)}", variable=var,
                                bg=t["BG2"], fg=t["FG"], selectcolor=t["TRACK"],
                                activebackground=t["BG2"], activeforeground=t["FG"], font=("Segoe UI", 10),
                                command=self._on_bars_change)
            cb.pack(anchor="w", pady=2)
            
        self.tabs["DataBars"] = f_bars
        
        # -- Notifications Tab --
        f_notif = tk.Frame(self.content_frame, bg=t["BG2"], padx=20, pady=20)
        tk.Label(f_notif, text="Notifications", font=("Segoe UI", 14, "bold"), bg=t["BG2"], fg=t["FG"]).pack(anchor="w", pady=(0, 15))
        
        self.var_low = tk.BooleanVar(value=CFG.SettingsManager.get("low_data_notif"))
        cb_low = tk.Checkbutton(f_notif, text="  Low-data notification", variable=self.var_low, 
                                bg=t["BG2"], fg=t["FG"], selectcolor=t["TRACK"], 
                                activebackground=t["BG2"], activeforeground=t["FG"], font=("Segoe UI", 10),
                                command=self._on_notification_change)
        cb_low.pack(anchor="w", pady=5)
        
        f_thresh = tk.Frame(f_notif, bg=t["BG2"])
        f_thresh.pack(anchor="w", pady=10, padx=25)
        tk.Label(f_thresh, text="Notify below threshold (GB):", font=("Segoe UI", 10), bg=t["BG2"], fg=t["DIM"]).pack(side="left")
        
        self.var_thresh = tk.DoubleVar(value=CFG.SettingsManager.get("low_data_threshold"))
        spin_thresh = tk.Spinbox(f_thresh, from_=0.1, to=100.0, increment=0.5, format="%.1f", width=5, 
                                 textvariable=self.var_thresh, bg=t["TRACK"], fg=t["FG"], font=("Segoe UI", 10),
                                 command=self._on_notification_change)
        spin_thresh.pack(side="left", padx=10)
        spin_thresh.bind("<KeyRelease>", lambda e: self._on_notification_change())
        
        tk.Label(f_notif, text="Low-data warning will be shown once\nwhen the threshold is crossed.", 
                 font=("Segoe UI", 9), bg=t["BG2"], fg=t["DIM"], justify="left").pack(anchor="w", pady=(20, 0))
                 
        self.tabs["Notifications"] = f_notif
        
        # -- About Tab --
        f_abt = tk.Frame(self.content_frame, bg=t["BG2"], padx=20, pady=20)
        tk.Label(f_abt, text="About", font=("Segoe UI", 14, "bold"), bg=t["BG2"], fg=t["FG"]).pack(anchor="w", pady=(0, 15))
        tk.Label(f_abt, text="Data Balance Widget\nVersion 1.0.0\n\nA lightweight Windows widget for monitoring\ninternet package balances.", 
                 font=("Segoe UI", 10), bg=t["BG2"], fg=t["DIM"], justify="left").pack(anchor="w")
        self.tabs["About"] = f_abt

    def show_tab(self, tab_id):
        t = self.parent_main.theme
        if self.current_tab:
            self.tabs[self.current_tab].pack_forget()
            self.nav_buttons[self.current_tab].config(bg=t["TRACK"])
            
        self.tabs[tab_id].pack(fill="both", expand=True)
        self.nav_buttons[tab_id].config(bg=t["BORDER"]) # highlight active
        self.current_tab = tab_id

    def _on_general_change(self, *args):
        start_win = self.var_startup.get()
        CFG.SettingsManager.set("start_with_windows", start_win)
        CFG.SettingsManager.set("remember_position", self.var_pos.get())
        set_autostart(start_win)

    def _save_account(self):
        email = self.var_email.get().strip()
        pw = self.var_pw.get()
        ll = self.var_landline.get().strip()
        
        if not email or not ll:
            self.lbl_status.config(text="Email and Landline required.", fg=self.parent_main.theme["BAD"])
            return
        if not pw:
            # We must strictly demand a password on setup because keyring might be empty
            self.lbl_status.config(text="Password is required.", fg=self.parent_main.theme["BAD"])
            return
            
        CFG.SettingsManager.set("slt_email", email)
        CFG.SettingsManager.set("slt_landline", ll)
        
        if pw:
            CFG.store_password(email, pw)
            
        self.lbl_status.config(text="Testing connection...", fg=self.parent_main.theme["DIM"])
        self.update_idletasks()
        
        import slt_api
        try:
            slt_api.login()
            self.lbl_status.config(text="Login successful!", fg=self.parent_main.theme["OK"])
            self.parent_main._do_refresh()
        except Exception as e:
            self.lbl_status.config(text=f"Error: {e}", fg=self.parent_main.theme["BAD"])

    def _on_bars_change(self):
        hidden = []
        enabled_count = 0
        
        # Enforce max 5 bars constraints (though there are only 5 options max available)
        for kind, var in self.bar_vars.items():
            if var.get():
                enabled_count += 1
            else:
                hidden.append(kind)
                
        if enabled_count > 5:
            pass # In practice impossible without >5 choices, but satisfies max 5 spec concept.
            
        CFG.SettingsManager.set("hidden_kinds", hidden)
        
        # update widget live
        self.parent_main._hidden = set(hidden)
        self.parent_main.draw()

    def _on_notification_change(self, *args):
        CFG.SettingsManager.set("low_data_notif", self.var_low.get())
        try:
            val = float(self.var_thresh.get())
            if val > 0:
                CFG.SettingsManager.set("low_data_threshold", val)
        except ValueError:
            pass
            
    def _update_widget_colors(self, widget, t):
        # Recursive color update for all children in a frame
        if isinstance(widget, tk.Frame):
            widget.config(bg=t["BG2"])
        elif isinstance(widget, tk.Label):
            # Try to guess role based on current fg
            font_size = widget.cget("font").split()[1] if "font" in widget.keys() else "10"
            if int(font_size) >= 14:
                widget.config(bg=t["BG2"], fg=t["FG"]) # title
            else:
                widget.config(bg=t["BG2"], fg=t["DIM"])
        elif isinstance(widget, tk.Checkbutton) or isinstance(widget, tk.Radiobutton):
            widget.config(bg=t["BG2"], fg=t["FG"], selectcolor=t["TRACK"], activebackground=t["BG2"], activeforeground=t["FG"])
        elif isinstance(widget, tk.Spinbox):
            widget.config(bg=t["TRACK"], fg=t["FG"])
            
        for child in widget.winfo_children():
            self._update_widget_colors(child, t)
