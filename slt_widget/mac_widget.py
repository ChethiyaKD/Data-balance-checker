"""macOS menu bar widget. Same backend as the Windows widget, shows the main package's remaining percentage in the menu bar."""
import os
import subprocess
import sys
import threading
import time

import rumps

import config as CFG
import slt_api as api

if getattr(sys, "frozen", False):
    import keyring
    import keyring.backends.macOS
    keyring.set_keyring(keyring.backends.macOS.Keyring())

STATUS_ICONS = {"OK": "\U0001F7E2", "WARN": "\U0001F7E1", "BAD": "\U0001F534"}
LAUNCH_AGENT_LABEL = "com.sltwidget.menubar"
LAUNCH_AGENT_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{LAUNCH_AGENT_LABEL}.plist")


def notify(title, message):
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=False)


def status_for(frac_remaining):
    if frac_remaining > 0.25:
        return "OK"
    if frac_remaining > 0.1:
        return "WARN"
    return "BAD"


class MacWidget(rumps.App):
    def __init__(self):
        super().__init__("SLT Data", title="…", quit_button=None)
        self.data = self.error = None
        self._last_refresh = 0.0

        self.item_details = rumps.MenuItem("Loading…")
        self.item_updated = rumps.MenuItem("Updated: never")
        self.item_refresh = rumps.MenuItem("Refresh Now", callback=self.refresh)

        self.item_notif = rumps.MenuItem("Low-data notification", callback=self.toggle_notif)
        self.item_notif.state = CFG.SettingsManager.get("low_data_notif")

        self.item_login = rumps.MenuItem("Start at Login", callback=self.toggle_login)
        self.item_login.state = CFG.SettingsManager.get("start_with_windows")

        self.menu = [
            self.item_details,
            self.item_updated,
            None,
            self.item_refresh,
            None,
            rumps.MenuItem("Set Email…", callback=self.set_email),
            rumps.MenuItem("Set Password…", callback=self.set_password),
            rumps.MenuItem("Set Subscriber ID…", callback=self.set_landline),
            None,
            self.item_notif,
            rumps.MenuItem("Set Threshold (GB)…", callback=self.set_threshold),
            self.item_login,
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

        self._sync_launch_agent(self.item_login.state)

        if not CFG.SettingsManager.get("slt_email") or not CFG.SettingsManager.get("slt_subscriber_id"):
            self.title = "⚠"
            self.item_details.title = "Set your MySLT email, password and subscriber ID first"
        else:
            self.refresh(None)

        rumps.Timer(self._tick, 60).start()

    def _tick(self, _timer):
        period = CFG.SettingsManager.get("refresh_period")
        if period and time.time() - self._last_refresh >= period * 60:
            self.refresh(None)

    def refresh(self, _sender):
        self._last_refresh = time.time()
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            self.data, self.error = api.summarise(), None
        except Exception as ex:
            self.data, self.error = None, str(ex)
        self._render()

    def _render(self):
        if self.error:
            self.title = "⚠"
            self.item_details.title = self.error
            self.item_updated.title = "Updated: —"
            return

        d = self.data
        standard = self._standard_row(d["rows"])
        if standard:
            remaining_pct = int(round((1 - standard["frac"]) * 100))
        else:
            remaining_pct = 0
        status = status_for(remaining_pct / 100)

        self.title = f"{STATUS_ICONS[status]} {remaining_pct}%"
        self.item_details.title = "  |  ".join(
            f"{r['name']}: {r['remaining']:.1f} {r['unit']} left" for r in d["rows"]
        ) or "No data"
        self.item_updated.title = f"Updated: {d['reported']}"

        self._check_low_data(standard)

    def _standard_row(self, rows):
        pkg_rows = [r for r in rows if r["kind"] == "package"]
        for r in pkg_rows:
            if r["name"].strip().lower() == "standard":
                return r
        return pkg_rows[0] if pkg_rows else None

    def _check_low_data(self, standard):
        if not standard or not CFG.SettingsManager.get("low_data_notif"):
            return
        thresh = CFG.SettingsManager.get("low_data_threshold")
        main_rem = standard["remaining"]

        sent = CFG.SettingsManager.load().get("_notif_sent", False)
        max_seen = CFG.SettingsManager.load().get("_max_balance_seen", 0.0)

        if main_rem > max_seen + 1.0:
            sent = False
            max_seen = main_rem
            CFG.SettingsManager.set("_notif_sent", False)
        elif main_rem > max_seen:
            max_seen = main_rem
        CFG.SettingsManager.set("_max_balance_seen", max_seen)

        if not sent and main_rem < thresh:
            CFG.SettingsManager.set("_notif_sent", True)
            notify("Low Internet Data", f"You have {main_rem:.1f} GB of data remaining.")

    def set_email(self, _sender):
        resp = rumps.Window("MySLT Email", "Account",
                             default_text=CFG.SettingsManager.get("slt_email") or "").run()
        if resp.clicked:
            CFG.SettingsManager.set("slt_email", resp.text.strip())

    def set_password(self, _sender):
        email = CFG.SettingsManager.get("slt_email")
        if not email:
            rumps.alert("Set your email first.")
            return
        resp = rumps.Window("MySLT Password", "Account", secure=True).run()
        if resp.clicked and resp.text:
            CFG.store_password(email, resp.text)
            self.refresh(None)

    def set_landline(self, _sender):
        resp = rumps.Window("Broadband Subscriber ID, e.g. RK1234567", "Account",
                             default_text=CFG.SettingsManager.get("slt_subscriber_id") or "").run()
        if resp.clicked:
            CFG.SettingsManager.set("slt_subscriber_id", resp.text.strip())
            self.refresh(None)

    def set_threshold(self, _sender):
        resp = rumps.Window("Notify below this many GB remaining", "Notifications",
                             default_text=str(CFG.SettingsManager.get("low_data_threshold"))).run()
        if resp.clicked:
            try:
                CFG.SettingsManager.set("low_data_threshold", float(resp.text))
            except ValueError:
                pass

    def toggle_notif(self, sender):
        sender.state = not sender.state
        CFG.SettingsManager.set("low_data_notif", sender.state)

    def toggle_login(self, sender):
        sender.state = not sender.state
        CFG.SettingsManager.set("start_with_windows", sender.state)
        self._sync_launch_agent(sender.state)

    def _sync_launch_agent(self, enable):
        if not enable:
            if os.path.exists(LAUNCH_AGENT_PATH):
                subprocess.run(["launchctl", "unload", LAUNCH_AGENT_PATH], check=False)
                os.remove(LAUNCH_AGENT_PATH)
            return

        os.makedirs(os.path.dirname(LAUNCH_AGENT_PATH), exist_ok=True)
        if getattr(sys, "frozen", False):
            args = f"<string>{sys.executable}</string>"
        else:
            args = f"<string>{sys.executable}</string>\n        <string>{os.path.abspath(__file__)}</string>"
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        {args}
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><false/>
</dict>
</plist>
"""
        with open(LAUNCH_AGENT_PATH, "w") as f:
            f.write(plist)
        subprocess.run(["launchctl", "unload", LAUNCH_AGENT_PATH], check=False)
        subprocess.run(["launchctl", "load", LAUNCH_AGENT_PATH], check=False)


if __name__ == "__main__":
    MacWidget().run()
