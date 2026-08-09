"""Personal build settings."""
import os

USERNAME      = ""
SUBSCRIBER_ID = ""          # e.g., "94" + landline_number[1:]
CLIENT_ID     = "b7402e9d66808f762ccedbe42c20668e"  # from MySLT portal JS

import json

STATE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SLTWidget")
SETTINGS_FILE = os.path.join(STATE_DIR, "settings.json")
POS_FILE      = os.path.join(STATE_DIR, "pos.json")

MANUAL_COOLDOWN_SECONDS = 300  # 5 min cooldown for manual refresh button
SHOW_ADDONS_DETAIL     = True

DEFAULT_SETTINGS = {
    "refresh_period": 15,       # minutes, 0 means manual
    "theme": "Blue",
    "hidden_kinds": [],
    "low_data_notif": True,
    "low_data_threshold": 5.0,  # GB
    "start_with_windows": True,
    "remember_position": True,
    "hide_details": False,
    "slt_email": "",
    "slt_landline": ""
}

ALL_KINDS = ["package", "addon", "extra_gb_data_summary",
             "bonus_data_summary", "free_data_summary"]

KIND_LABELS = {
    "package":                "Main Package",
    "addon":                  "Add-Ons",
    "extra_gb_data_summary":  "Extra GB",
    "bonus_data_summary":     "Bonus Data",
    "free_data_summary":      "Free Data",
}

THEMES = {
    "Blue": {
        "BG2": "#132b44", "FG": "#e8f1f8", "DIM": "#7f9bb3", "ACCENT": "#1e90ff",
        "TRACK": "#1b3350", "OK": "#3fc46b", "WARN": "#e0a13a", "BAD": "#e0603a",
        "BORDER": "#264060", "REFRESH_ICON_CLR": "#5ba8ed", "REFRESH_ICON_DIM": "#3a5570",
        "MENU_BG": "#1a2d42"
    },
    "Black": {
        "BG2": "#161616", "FG": "#ffffff", "DIM": "#888888", "ACCENT": "#aaaaaa",
        "TRACK": "#292929", "OK": "#3fc46b", "WARN": "#e0a13a", "BAD": "#e0603a",
        "BORDER": "#333333", "REFRESH_ICON_CLR": "#cccccc", "REFRESH_ICON_DIM": "#666666",
        "MENU_BG": "#222222"
    },
    "White": {
        "BG2": "#f5f5f5", "FG": "#222222", "DIM": "#666666", "ACCENT": "#1e90ff",
        "TRACK": "#e0e0e0", "OK": "#3fc46b", "WARN": "#e0a13a", "BAD": "#e0603a",
        "BORDER": "#cccccc", "REFRESH_ICON_CLR": "#1e90ff", "REFRESH_ICON_DIM": "#999999",
        "MENU_BG": "#ffffff"
    }
}

class SettingsManager:
    @classmethod
    def load(cls):
        s = DEFAULT_SETTINGS.copy()
        try:
            with open(SETTINGS_FILE, "r") as f:
                s.update(json.load(f))
        except Exception:
            pass
        return s

    @classmethod
    def save(cls, settings_dict):
        os.makedirs(STATE_DIR, exist_ok=True)
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings_dict, f)
        except Exception:
            pass

    @classmethod
    def get(cls, key):
        return cls.load().get(key, DEFAULT_SETTINGS.get(key))

    @classmethod
    def set(cls, key, value):
        s = cls.load()
        s[key] = value
        cls.save(s)


def get_password(username):
    """Resolution order: env var -> Windows Credential Manager -> prompt once."""
    if not username: return None
    pw = os.environ.get("MYSLT_PASSWORD")
    if pw:
        return pw
    try:
        import keyring
        pw = keyring.get_password("myslt-widget", username)
        if pw:
            return pw
    except ImportError:
        pass
    return None


def store_password(username, pw):
    if not username: return False
    try:
        import keyring
        keyring.set_password("myslt-widget", username, pw)
        return True
    except ImportError:
        return False
