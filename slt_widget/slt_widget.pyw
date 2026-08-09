"""Frameless always-on-top widget. Drag to move, right-click for menu."""
import json, os, socket, threading, time, tkinter as tk
from tkinter import font as tkfont

import config as CFG
import slt_api as api

# ── colours ──────────────────────────────────────────────────────────
TRANSP   = "#010101"        # transparency key (invisible)
# Global hardcoded colors are removed. The widget now uses self.theme

# ── persistent paths ────────────────────────────────────────────────
POS_FILE      = os.path.join(CFG.STATE_DIR, "pos.json")
SETTINGS_FILE = os.path.join(CFG.STATE_DIR, "settings.json")

# ── network probe ───────────────────────────────────────────────────
def _net_ok(host="omniscapp.slt.lk", port=443, timeout=4):
    """Quick TCP-connect probe; no HTTP overhead."""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except OSError:
        return False


# ── round-rect helper for canvas ────────────────────────────────────
def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Draw a rounded rectangle on *canvas*."""
    pts = [
        x1+r, y1,   x2-r, y1,   x2, y1,   x2, y1+r,
        x2, y2-r,   x2, y2,     x2-r, y2,  x1+r, y2,
        x1, y2,     x1, y2-r,   x1, y1+r,  x1, y1,
        x1+r, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


# ════════════════════════════════════════════════════════════════════
class Widget(tk.Tk):
    WIDTH = 320

    @property
    def theme(self):
        t = CFG.SettingsManager.get("theme")
        return CFG.THEMES.get(t, CFG.THEMES["Blue"])

    def apply_theme(self):
        t = self.theme
        self.menu.config(bg=t["MENU_BG"], fg=t["FG"], activebackground=t["ACCENT"], activeforeground=t["FG"])
        self._settings_menu.config(bg=t["MENU_BG"], fg=t["FG"], activebackground=t["ACCENT"], activeforeground=t["FG"])
        self._period_menu.config(bg=t["MENU_BG"], fg=t["FG"], activebackground=t["ACCENT"], activeforeground=t["FG"])
        self.draw()

    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.attributes("-alpha", 0.92)
        self.configure(bg=TRANSP)
        self.wm_attributes("-transparentcolor", TRANSP)

        try:
            x, y = json.load(open(POS_FILE))
        except Exception:
            x, y = 60, 60
        self.geometry(f"{self.WIDTH}x420+{x}+{y}")

        # ── fonts ────────────────────────────────────────────────────
        self.f_title = tkfont.Font(family="Segoe UI Semibold", size=11)
        self.f_row   = tkfont.Font(family="Segoe UI", size=9)
        self.f_small = tkfont.Font(family="Segoe UI", size=8)
        self.f_icon  = tkfont.Font(family="Segoe UI", size=12, weight="bold")

        # ── canvas ───────────────────────────────────────────────────
        self.canvas = tk.Canvas(self, bg=TRANSP, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=0, pady=0)

        for w in (self, self.canvas):
            w.bind("<Button-1>", self._grab)
            w.bind("<B1-Motion>", self._drag)
            w.bind("<Button-3>", self._menu_popup)

        self.canvas.bind("<ButtonRelease-1>", self._click_check)

        # ── state ────────────────────────────────────────────────────
        self.data = self.error = None
        self._last_refresh = 0.0
        self._net_was_up = True
        self._refresh_btn_bbox = None    # (x1, y1, x2, y2) for click detect

        self._menu_btn_bbox = None       # (x1, y1, x2, y2) for click detect
        self._auto_tick_id = None

        # hidden kinds (must be set before _build_menu)
        self._hidden = set(CFG.SettingsManager.get("hidden_kinds"))

        # ── right-click menu ─────────────────────────────────────────
        self._build_menu()

        # ── initial fetch + timers ───────────────────────────────────
        if not CFG.SettingsManager.get("slt_email") or not CFG.SettingsManager.get("slt_landline"):
            self.error = "Please setup an account in Settings."
            self.after(500, self._open_settings)
        else:
            self._do_refresh()
            self._reset_auto_tick()
            self.after(30_000, self._net_poll)

    # ── menu ─────────────────────────────────────────────────────────
    def _build_menu(self):
        t = self.theme
        self.menu = tk.Menu(self, tearoff=0, bg=t["MENU_BG"], fg=t["FG"],
                            activebackground=t["ACCENT"], activeforeground=t["FG"],
                            relief="flat", bd=0, activeborderwidth=0)
        self.menu.add_command(label="  Refresh now", command=self._manual_refresh)
        self.menu.add_separator()

        # refresh period sub-menu
        self._period_menu = tk.Menu(self.menu, tearoff=0, bg=t["MENU_BG"], fg=t["FG"],
                                    activebackground=t["ACCENT"], activeforeground=t["FG"], relief="flat", bd=0, activeborderwidth=0)
        self._period_var = tk.IntVar(value=CFG.SettingsManager.get("refresh_period"))
        
        periods = [("15 minutes", 15), ("30 minutes", 30),
                   ("1 hour", 60), ("3 hours", 180), ("Manual", 0)]
        for label, val in periods:
            self._period_menu.add_radiobutton(label=label, variable=self._period_var, value=val,
                                              command=self._change_period)
        
        self.menu.add_cascade(label="  Refresh period", menu=self._period_menu)
        
        self.menu.add_separator()
        
        self._hide_var = tk.BooleanVar(value=CFG.SettingsManager.get("hide_details"))
        self.menu.add_checkbutton(label="  Hide details (Privacy)", variable=self._hide_var, command=self._toggle_hide)
        
        self.menu.add_separator()
        self.menu.add_command(label="  Settings", command=self._open_settings)

        self.menu.add_separator()
        self.menu.add_command(label="  Exit", command=self.close)

    def _toggle_hide(self):
        CFG.SettingsManager.set("hide_details", self._hide_var.get())
        self.draw()

    def _open_settings(self):
        import settings_ui
        if hasattr(self, "settings_win") and self.settings_win.winfo_exists():
            self.settings_win.focus_force()
            return
        self.settings_win = settings_ui.SettingsWindow(self)

    def _change_period(self):
        new_val = self._period_var.get()
        CFG.SettingsManager.set("refresh_period", new_val)
        self._reset_auto_tick()

    # ── drag / position ──────────────────────────────────────────────
    def _grab(self, e):
        self._drag_moved = False
        # Restrict widget dragging strictly to the top header portion
        if e.y > 45:
            self._drag_data = None
            return
        self._drag_data = (e.x_root - self.winfo_x(),
                           e.y_root - self.winfo_y())

    def _drag(self, e):
        if getattr(self, "_drag_data", None) is None:
            return
        self._drag_moved = True
        dx, dy = self._drag_data
        self.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    def _menu_popup(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def _click_check(self, e):
        """Detect click on refresh button (only if no drag occurred)."""
        if getattr(self, "_drag_moved", False):
            return
        bb = self._refresh_btn_bbox
        if bb and bb[0] <= e.x <= bb[2] and bb[1] <= e.y <= bb[3]:
            self._manual_refresh()
            return
            
        mb = self._menu_btn_bbox
        if mb and mb[0] <= e.x <= mb[2] and mb[1] <= e.y <= mb[3]:
            self._menu_popup(e)
            return

    def close(self):
        os.makedirs(CFG.STATE_DIR, exist_ok=True)
        with open(POS_FILE, "w") as f:
            json.dump([self.winfo_x(), self.winfo_y()], f)
        self.destroy()

    # ── refresh logic ────────────────────────────────────────────────
    def _cooldown_remaining(self):
        elapsed = time.time() - self._last_refresh
        return max(0, CFG.MANUAL_COOLDOWN_SECONDS - elapsed)

    def _manual_refresh(self):
        cd = self._cooldown_remaining()
        if cd > 0:
            if hasattr(self, "_rate_msg_id"):
                self.canvas.delete(self._rate_msg_id)
            bb = self._refresh_btn_bbox
            if bb:
                self._rate_msg_id = self.canvas.create_text(bb[0] - 4, bb[1] + 8, anchor="e",
                                                            text=f"Please wait {int(cd)}s", 
                                                            fill=self.theme["WARN"], font=self.f_small)
                self.after(2000, lambda: self.canvas.delete(self._rate_msg_id) if self.canvas.winfo_exists() else None)
            return   # rate-limited
        
        # simple animation for refresh button
        self.canvas.itemconfig("refresh_btn", fill=self.theme["FG"])
        self.update_idletasks()
        self.after(150, self._do_refresh)

    def _do_refresh(self):
        self._last_refresh = time.time()
        self._just_refreshed = True
        threading.Thread(target=self._fetch, daemon=True).start()

    def _reset_auto_tick(self):
        if self._auto_tick_id:
            self.after_cancel(self._auto_tick_id)
            self._auto_tick_id = None
        period = CFG.SettingsManager.get("refresh_period")
        if period > 0:
            self._auto_tick_id = self.after(period * 60_000, self._auto_tick)

    def _auto_tick(self):
        self._do_refresh()
        self._reset_auto_tick()

    def _net_poll(self):
        """Check network every 30 s; refresh on reconnect."""
        def check():
            up = _net_ok()
            if up and not self._net_was_up:
                self.after(0, self._do_refresh)
            self._net_was_up = up
        threading.Thread(target=check, daemon=True).start()
        self.after(30_000, self._net_poll)

    def _fetch(self):
        try:
            self.data, self.error = api.summarise(), None
            self.after(0, self._check_low_data, self.data)
        except Exception as ex:
            self.error = str(ex)
        self.after(0, self.draw)

    def _check_low_data(self, d):
        if not CFG.SettingsManager.get("low_data_notif"):
            return
            
        thresh = CFG.SettingsManager.get("low_data_threshold")
        
        # calculate main package remaining balance
        main_rem = sum(r["remaining"] for r in d["rows"] if r["kind"] == "package")
        
        sent = CFG.SettingsManager.load().get("_notif_sent", False)
        max_seen = CFG.SettingsManager.load().get("_max_balance_seen", 0.0)
        
        # Reset if balance renewed significantly (> 1GB jump)
        if main_rem > max_seen + 1.0:
            sent = False
            max_seen = main_rem
            CFG.SettingsManager.set("_notif_sent", False)
        elif main_rem > max_seen:
            max_seen = main_rem
            
        CFG.SettingsManager.set("_max_balance_seen", max_seen)
        
        # Trigger single notification if below threshold
        if not sent and main_rem < thresh:
            CFG.SettingsManager.set("_notif_sent", True)
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(
                    "Low Internet Data",
                    f"You have {main_rem:.1f} GB of data remaining.",
                    duration=5,
                    threaded=True
                )
            except Exception as e:
                print("Toast failed:", e)

    # ── drawing ──────────────────────────────────────────────────────
    def draw(self):
        c = self.canvas
        c.delete("all")
        W = self.WIDTH
        PAD = 14
        cw = W - 2 * PAD  # content width

        t = self.theme
        if self.error:
            self._draw_error(c, PAD, cw, t)
            return
        if not self.data:
            self.geometry(f"{W}x80")
            self.update_idletasks()
            _round_rect(c, 6, 6, W - 6, 70, r=14,
                        fill=t["BG2"], outline=t["BORDER"], width=1)
            c.create_text(PAD, 30, anchor="nw", text="Loading...",
                          fill=t["DIM"], font=self.f_row)
            return

        d = self.data

        # ── pass 1: calculate total height ────────────────────────────
        y = PAD + 2          # header starts here
        y += 28              # header height
        y += 8               # separator gap
        
        if CFG.SettingsManager.get("hide_details"):
            visible = []
        else:
            visible = [r for r in d["rows"] if r["kind"] not in self._hidden]
            
        for _ in visible:
            y += 18 + 7 + 14  # label + bar + gap
        y += 2               # footer gap
        y += 16              # footer text height

        panel_h = y + 18     # bottom padding inside panel
        win_h = panel_h + 14 # padding below panel

        # ── set geometry first so canvas has room ─────────────────────
        self.geometry(f"{W}x{win_h}")
        self.update_idletasks()

        # ── glass background panel ───────────────────────────────────
        _round_rect(c, 6, 6, W - 6, panel_h, r=14,
                    fill=t["BG2"], outline=t["BORDER"], width=1, tags="bg_panel")

        # ── pass 2: draw content ──────────────────────────────────────
        y = PAD + 2

        # ── header ───────────────────────────────────────────────────
        hide_details = CFG.SettingsManager.get("hide_details")
        
        if not hide_details:
            c.create_text(PAD, y, anchor="nw", text=d["package"],
                          fill=t["FG"], font=self.f_title)
            st_col = t["OK"] if d["status"] == "NORMAL" else t["WARN"]
            c.create_text(W - PAD - 20, y + 3, anchor="ne", text=d["status"],
                          fill=st_col, font=self.f_small)

        # ⋮ menu button
        # Adjusted Y alignment by moving upward further.
        menu_id = c.create_text(W - PAD + 2, y - 1, anchor="ne", text="⋮",
                                fill=t["DIM"], font=self.f_icon, tags="menu_btn")
        bb = c.bbox(menu_id)
        if bb:
            self._menu_btn_bbox = (bb[0] - 6, bb[1] - 6, bb[2] + 6, bb[3] + 6)
        else:
            self._menu_btn_bbox = None

        y += 28

        # ── thin separator ───────────────────────────────────────────
        c.create_line(PAD, y, W - PAD, y, fill=t["BORDER"], width=1)
        y += 8

        # ── data rows ────────────────────────────────────────────────
        for i, r in enumerate(visible):
            y = self._draw_row(c, PAD, cw, y, r, t)
            if i < len(visible) - 1:
                c.create_line(PAD + 10, y - 4, W - PAD - 10, y - 4,
                              fill=t["BORDER"], width=1, dash=(2, 4))

        # ── footer ───────────────────────────────────────────────────
        y += 2
        upd_text = c.create_text(PAD, y, anchor="nw",
                                 text="Updated " + d["reported"],
                                 fill=t["DIM"], font=self.f_small)

        if getattr(self, "_just_refreshed", False):
            self._just_refreshed = False
            # simple blink animation to green when updated
            c.itemconfig(upd_text, fill=t["OK"])
            self.after(500, lambda: c.itemconfig(upd_text, fill=t["DIM"]) if c.winfo_exists() else None)

        # ── refresh button ───────────────────────────────────────────
        self._draw_refresh_btn(c, W - PAD, y, t)

    def _draw_row(self, c, pad, cw, y, r, t):
        """Draw one data row; returns new y."""
        # label (truncated if too long)
        if r["expiry"]:
            label = f"{r['name']}  (till {r['expiry']})"
        else:
            label = r["name"]

        max_label_w = int(cw * 0.6)
        while self.f_small.measure(label) > max_label_w and len(label) > 4:
            label = label[:-4] + "..."

        c.create_text(pad, y, anchor="nw", text=label,
                      fill=t["DIM"], font=self.f_small)

        # remaining value
        c.create_text(pad + cw, y, anchor="ne",
                      text=f"{r['remaining']:.1f} {r['unit']} left",
                      fill=t["FG"], font=self.f_row)
        y += 18

        # ── progress bar (rounded) ───────────────────────────────────
        bar_h = 7
        bar_r = 3
        # track
        _round_rect(c, pad, y, pad + cw, y + bar_h, r=bar_r,
                    fill=t["TRACK"], outline="")
        # fill
        frac = min(r["frac"], 1.0)
        col = t["OK"] if frac < 0.75 else (t["WARN"] if frac < 0.9 else t["BAD"])
        if frac > 0.02:
            fill_w = max(int(cw * frac), bar_r * 2 + 1)
            _round_rect(c, pad, y, pad + fill_w, y + bar_h, r=bar_r,
                        fill=col, outline="")

        y += bar_h + 14
        return y

    def _draw_refresh_btn(self, c, x, y, t):
        """Draw circular-arrow refresh icon at (x, y)."""
        on_cooldown = self._cooldown_remaining() > 0
        clr = t["REFRESH_ICON_DIM"] if on_cooldown else t["REFRESH_ICON_CLR"]

        # unicode circular arrow
        txt_id = c.create_text(x, y, anchor="ne", text="\u21BB",
                               fill=clr, font=self.f_icon, tags="refresh_btn")
        bb = c.bbox(txt_id)
        if bb:
            # expand hit area a bit
            self._refresh_btn_bbox = (bb[0] - 4, bb[1] - 4,
                                      bb[2] + 4, bb[3] + 4)
        else:
            self._refresh_btn_bbox = None

    def _draw_error(self, c, pad, cw, t):
        W = self.WIDTH
        c.create_text(pad, 18, anchor="nw", text="Data Balance",
                      fill=t["FG"], font=self.f_title)
        c.create_text(pad, 46, anchor="nw", text=self.error, fill=t["BAD"],
                      font=self.f_small, width=cw)
        c.create_text(pad, 120, anchor="nw",
                      text="Right-click > Refresh now",
                      fill=t["DIM"], font=self.f_small)
        _round_rect(c, 6, 6, W - 6, 160, r=14,
                    fill=t["BG2"], outline=t["BORDER"], width=1, tags="bg_panel")
        c.tag_lower("bg_panel")
        self.geometry(f"{W}x170")


if __name__ == "__main__":
    # Sync autostart registry state on boot
    import settings_ui
    settings_ui.set_autostart(CFG.SettingsManager.get("start_with_windows"))
    
    Widget().mainloop()
