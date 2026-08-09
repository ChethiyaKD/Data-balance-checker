"""Frameless always-on-top widget. Drag to move, right-click for menu."""
import json, os, socket, threading, time, tkinter as tk
from tkinter import font as tkfont

import config as CFG
import slt_api as api

# ── colours ──────────────────────────────────────────────────────────
TRANSP   = "#010101"        # transparency key (invisible)
BG       = "#0d1b2a"
BG2      = "#132b44"      # slightly lighter for glass panel
FG       = "#e8f1f8"
DIM      = "#7f9bb3"
ACCENT   = "#1e90ff"
TRACK    = "#1b3350"
OK       = "#3fc46b"
WARN     = "#e0a13a"
BAD      = "#e0603a"
BORDER   = "#264060"
REFRESH_ICON_CLR = "#5ba8ed"
REFRESH_ICON_DIM = "#3a5570"

# ── persistent paths ────────────────────────────────────────────────
POS_FILE      = os.path.join(CFG.STATE_DIR, "pos.json")
SETTINGS_FILE = os.path.join(CFG.STATE_DIR, "settings.json")

# ── settings helpers ────────────────────────────────────────────────
ALL_KINDS = ["package", "addon", "extra_gb_data_summary",
             "bonus_data_summary", "free_data_summary"]

KIND_LABELS = {
    "package":                "Main Package",
    "addon":                  "Add-Ons",
    "extra_gb_data_summary":  "Extra GB",
    "bonus_data_summary":     "Bonus Data",
    "free_data_summary":      "Free Data",
}


def _load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(s):
    os.makedirs(CFG.STATE_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f)


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

        # hidden kinds (must be set before _build_menu)
        settings = _load_settings()
        self._hidden = set(settings.get("hidden_kinds",
                                        list(CFG.HIDDEN_KINDS_DEFAULT)))

        # ── right-click menu ─────────────────────────────────────────
        self._build_menu()

        # ── initial fetch + timers ───────────────────────────────────
        self._do_refresh()
        self.after(CFG.REFRESH_MINUTES * 60_000, self._auto_tick)
        self.after(30_000, self._net_poll)

    # ── menu ─────────────────────────────────────────────────────────
    def _build_menu(self):
        self.menu = tk.Menu(self, tearoff=0, bg="#1a2d42", fg=FG,
                            activebackground=ACCENT, activeforeground=FG,
                            relief="flat", bd=0)
        self.menu.add_command(label="  Refresh now", command=self._manual_refresh)
        self.menu.add_command(label="  Open MySLT",
                              command=lambda: os.startfile("https://myslt.slt.lk"))
        self.menu.add_separator()

        # settings sub-menu
        self._settings_menu = tk.Menu(self.menu, tearoff=0, bg="#1a2d42",
                                       fg=FG, activebackground=ACCENT,
                                       activeforeground=FG, relief="flat", bd=0)
        self._kind_vars = {}
        for kind in ALL_KINDS:
            var = tk.BooleanVar(value=(kind not in self._hidden))
            self._kind_vars[kind] = var
            self._settings_menu.add_checkbutton(
                label=f"  {KIND_LABELS.get(kind, kind)}",
                variable=var,
                command=lambda k=kind: self._toggle_kind(k))
        self.menu.add_cascade(label="  Settings", menu=self._settings_menu)
        self.menu.add_separator()
        self.menu.add_command(label="  Exit", command=self.close)

    def _toggle_kind(self, kind):
        if self._kind_vars[kind].get():
            self._hidden.discard(kind)
        else:
            self._hidden.add(kind)
        # persist
        settings = _load_settings()
        settings["hidden_kinds"] = list(self._hidden)
        _save_settings(settings)
        self.draw()

    # ── drag / position ──────────────────────────────────────────────
    def _grab(self, e):
        self._drag_data = (e.x_root - self.winfo_x(),
                           e.y_root - self.winfo_y())
        self._drag_moved = False

    def _drag(self, e):
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
                                                            fill=WARN, font=self.f_small)
                self.after(2000, lambda: self.canvas.delete(self._rate_msg_id) if self.canvas.winfo_exists() else None)
            return   # rate-limited
        
        # simple animation for refresh button
        self.canvas.itemconfig("refresh_btn", fill=FG)
        self.update_idletasks()
        self.after(150, self._do_refresh)

    def _do_refresh(self):
        self._last_refresh = time.time()
        self._just_refreshed = True
        threading.Thread(target=self._fetch, daemon=True).start()

    def _auto_tick(self):
        self._do_refresh()
        self.after(CFG.REFRESH_MINUTES * 60_000, self._auto_tick)

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
        except Exception as ex:
            self.error = str(ex)
        self.after(0, self.draw)

    # ── drawing ──────────────────────────────────────────────────────
    def draw(self):
        c = self.canvas
        c.delete("all")
        W = self.WIDTH
        PAD = 14
        cw = W - 2 * PAD  # content width

        if self.error:
            self._draw_error(c, PAD, cw)
            return
        if not self.data:
            self.geometry(f"{W}x80")
            self.update_idletasks()
            _round_rect(c, 6, 6, W - 6, 70, r=14,
                        fill=BG2, outline=BORDER, width=1)
            c.create_text(PAD, 30, anchor="nw", text="Loading...",
                          fill=DIM, font=self.f_row)
            return

        d = self.data

        # ── pass 1: calculate total height ────────────────────────────
        y = PAD + 2          # header starts here
        y += 28              # header height
        y += 8               # separator gap
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
                    fill=BG2, outline=BORDER, width=1, tags="bg_panel")

        # ── pass 2: draw content ──────────────────────────────────────
        y = PAD + 2

        # ── header ───────────────────────────────────────────────────
        c.create_text(PAD, y, anchor="nw", text=d["package"],
                      fill=FG, font=self.f_title)
        st_col = OK if d["status"] == "NORMAL" else WARN
        c.create_text(W - PAD, y + 3, anchor="ne", text=d["status"],
                      fill=st_col, font=self.f_small)
        y += 28

        # ── thin separator ───────────────────────────────────────────
        c.create_line(PAD, y, W - PAD, y, fill=BORDER, width=1)
        y += 8

        # ── data rows ────────────────────────────────────────────────
        for i, r in enumerate(visible):
            y = self._draw_row(c, PAD, cw, y, r)
            if i < len(visible) - 1:
                c.create_line(PAD + 10, y - 4, W - PAD - 10, y - 4,
                              fill=BORDER, width=1, dash=(2, 4))

        # ── footer ───────────────────────────────────────────────────
        y += 2
        upd_text = c.create_text(PAD, y, anchor="nw",
                                 text="Updated " + d["reported"],
                                 fill=DIM, font=self.f_small)

        if getattr(self, "_just_refreshed", False):
            self._just_refreshed = False
            # simple blink animation to green when updated
            c.itemconfig(upd_text, fill=OK)
            self.after(500, lambda: c.itemconfig(upd_text, fill=DIM) if c.winfo_exists() else None)

        # ── refresh button ───────────────────────────────────────────
        self._draw_refresh_btn(c, W - PAD, y)

    def _draw_row(self, c, pad, cw, y, r):
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
                      fill=DIM, font=self.f_small)

        # remaining value
        c.create_text(pad + cw, y, anchor="ne",
                      text=f"{r['remaining']:.1f} {r['unit']} left",
                      fill=FG, font=self.f_row)
        y += 18

        # ── progress bar (rounded) ───────────────────────────────────
        bar_h = 7
        bar_r = 3
        # track
        _round_rect(c, pad, y, pad + cw, y + bar_h, r=bar_r,
                    fill=TRACK, outline="")
        # fill
        frac = min(r["frac"], 1.0)
        col = OK if frac < 0.75 else (WARN if frac < 0.9 else BAD)
        if frac > 0.02:
            fill_w = max(int(cw * frac), bar_r * 2 + 1)
            _round_rect(c, pad, y, pad + fill_w, y + bar_h, r=bar_r,
                        fill=col, outline="")

        y += bar_h + 14
        return y

    def _draw_refresh_btn(self, c, x, y):
        """Draw circular-arrow refresh icon at (x, y)."""
        on_cooldown = self._cooldown_remaining() > 0
        clr = REFRESH_ICON_DIM if on_cooldown else REFRESH_ICON_CLR

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

    def _draw_error(self, c, pad, cw):
        W = self.WIDTH
        c.create_text(pad, 18, anchor="nw", text="MySLT",
                      fill=FG, font=self.f_title)
        c.create_text(pad, 46, anchor="nw", text=self.error, fill=BAD,
                      font=self.f_small, width=cw)
        c.create_text(pad, 120, anchor="nw",
                      text="Right-click > Refresh now",
                      fill=DIM, font=self.f_small)
        _round_rect(c, 6, 6, W - 6, 160, r=14,
                    fill=BG2, outline=BORDER, width=1, tags="bg_panel")
        c.tag_lower("bg_panel")
        self.geometry(f"{W}x170")


if __name__ == "__main__":
    Widget().mainloop()
