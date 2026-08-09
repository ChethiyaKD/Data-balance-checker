"""Personal build settings."""
import os

USERNAME      = "nimsara.tharinduvidyathilaka@gmail.com"
SUBSCRIBER_ID = "94362249018"          # "94" + telephoneno[1:]
CLIENT_ID     = "b7402e9d66808f762ccedbe42c20668e"  # from MySLT portal JS

REFRESH_MINUTES        = 120   # auto-refresh every 2 hours
MANUAL_COOLDOWN_SECONDS = 300  # 5 min cooldown for manual refresh button
SHOW_ADDONS_DETAIL     = True

# Row kinds that are hidden by default (user can toggle via right-click > Settings)
# Valid kinds: "package", "addon", "extra_gb_data_summary",
#              "bonus_data_summary", "free_data_summary"
HIDDEN_KINDS_DEFAULT = set()   # everything visible by default

STATE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                         "SLTWidget")


def get_password():
    """Resolution order: env var -> Windows Credential Manager -> prompt once."""
    pw = os.environ.get("MYSLT_PASSWORD")
    if pw:
        return pw
    try:
        import keyring
        pw = keyring.get_password("myslt-widget", USERNAME)
        if pw:
            return pw
    except ImportError:
        pass
    return None


def store_password(pw):
    try:
        import keyring
        keyring.set_password("myslt-widget", USERNAME, pw)
        return True
    except ImportError:
        return False
