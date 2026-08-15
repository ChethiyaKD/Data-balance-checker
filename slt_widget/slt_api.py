"""MySLT API client - personal build. Stdlib only."""
import base64, json, os, re, time, urllib.error, urllib.parse, urllib.request

import config as CFG

BASE = "https://omniscapp.slt.lk/slt/ext/api"
PORTAL = "https://myslt.slt.lk"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SLTWidget/1.0"

TOKENS = os.path.join(CFG.STATE_DIR, "tokens.json")
CIDFILE = os.path.join(CFG.STATE_DIR, "client_id.txt")


class SLTError(Exception): pass
class AuthError(SLTError): pass
class ClientIdError(SLTError): pass


def _req(url, data=None, headers=None, timeout=30):
    hdr = {"User-Agent": UA, "Accept": "application/json"}
    hdr.update(headers or {})
    r = urllib.request.Request(url, data=data, headers=hdr,
                               method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw, status = resp.read().decode("utf-8", "replace"), resp.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode("utf-8", "replace"), e.code
    except urllib.error.URLError as e:
        raise SLTError(f"Network error: {e.reason}")
    except TimeoutError:
        raise SLTError(f"Request timed out: {url}")
    try:
        return status, json.loads(raw), raw
    except ValueError:
        return status, None, raw


# ---------- client id ----------

def _probe(cid):
    """Junk-credential probe: empty-bodied 401 == key valid."""
    body = urllib.parse.urlencode({"username": "sltwidget_probe_000000",
                                   "password": "probe",
                                   "channelID": "WEB"}).encode()
    st, j, raw = _req(f"{BASE}/Account/Login", body,
                      {"Content-Type": "application/x-www-form-urlencoded",
                       "X-IBM-Client-Id": cid}, timeout=15)
    if st == 401 and not raw.strip():
        return True
    if j and j.get("moreInformation"):
        return False
    return st != 401


def discover_client_id():
    st, _, html = _req(PORTAL, timeout=60)
    if st != 200:
        raise ClientIdError(f"Cannot load portal (HTTP {st}).")
    ranked, seen = [], set()
    for p in re.findall(r'src="(/static/js/[^"]+\.js)"', html):
        _, _, js = _req(PORTAL + p, timeout=90)
        if not js:
            continue
        i = js.find("BBVAS")
        near = re.findall(r'["\']([a-f0-9]{32})["\']',
                          js[max(0, i - 4000): i + 4000]) if i > -1 else []
        for cid in near + re.findall(r'["\']([a-f0-9]{32})["\']', js):
            if cid not in seen:
                seen.add(cid); ranked.append(cid)
    for cid in ranked:
        try:
            if _probe(cid):
                return cid
        except SLTError:
            continue
    raise ClientIdError(
        "Auto-detect failed. Open MySLT, F12 > Network > reload, click any "
        "'BBVAS/...' request, copy 'X-IBM-Client-Id' into config.CLIENT_ID.")


def client_id():
    if hasattr(CFG, 'CLIENT_ID') and CFG.CLIENT_ID:
        return CFG.CLIENT_ID
    os.makedirs(CFG.STATE_DIR, exist_ok=True)
    if os.path.exists(CIDFILE):
        v = open(CIDFILE).read().strip()
        if v:
            return v
    cid = discover_client_id()
    open(CIDFILE, "w").write(cid)
    return cid


# ---------- auth ----------

def _jwt_exp(tok):
    try:
        p = tok.split(".")[1]; p += "=" * (-len(p) % 4)
        return int(json.loads(base64.urlsafe_b64decode(p)).get("exp", 0))
    except Exception:
        return int(time.time()) + 1800


def login():
    email = (CFG.SettingsManager.get("slt_email") or "").strip()
    if not email:
        raise AuthError("No email configured. Please login via Settings.")
    pw = CFG.get_password(email)
    if not pw:
        raise AuthError("No password found in keyring.")
    body = urllib.parse.urlencode({"username": email, "password": pw,
                                   "channelID": "WEB"}).encode()
    st, j, raw = _req(f"{BASE}/Account/Login", body,
                      {"Content-Type": "application/x-www-form-urlencoded",
                       "X-IBM-Client-Id": client_id()})
    if st == 401:
        if raw.strip() and j and j.get("moreInformation"):
            raise ClientIdError(j["moreInformation"])
        raise AuthError("Incorrect username or password. "
                        "Google-signup accounts must set one via Forgot Password.")
    tok = (j or {}).get("accessToken") or (j or {}).get("access_token")
    if not tok:
        raise AuthError(f"Login failed: {(j or {}).get('errorShow') or st}")
    os.makedirs(CFG.STATE_DIR, exist_ok=True)
    data = {"access_token": tok, "exp": _jwt_exp(tok)}
    with open(TOKENS, "w") as f:
        json.dump(data, f)
    try:
        os.chmod(TOKENS, 0o600)
    except OSError:
        pass
    return tok


def token(force=False):
    if not force and os.path.exists(TOKENS):
        try:
            t = json.load(open(TOKENS))
            if t.get("access_token") and t.get("exp", 0) - 120 > time.time():
                return t["access_token"]
        except (ValueError, OSError):
            pass
    return login()


def _get(path, params=None):
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"{BASE}/{path}{qs}"

    def call(t):
        return _req(url, None, {"Authorization": "bearer " + t,
                                "X-IBM-Client-Id": client_id()})
    st, j, _ = call(token())
    if st == 401:
        st, j, _ = call(token(force=True))
    if j is None:
        raise SLTError(f"Unexpected response (HTTP {st}).")
    if not j.get("isSuccess"):
        raise SLTError(j.get("errorShow") or j.get("errorMessege")
                       or f"Request failed (HTTP {st}).")
    return j.get("dataBundle")


def _get_sub_id():
    return (CFG.SettingsManager.get("slt_subscriber_id") or "").strip()

def usage_summary(): return _get("BBVAS/UsageSummary",
                                 {"subscriberID": _get_sub_id()})
def addons():        return _get("BBVAS/GetDashboardVASBundles",
                                 {"subscriberID": _get_sub_id()})
def extra_gb():      return _get("BBVAS/ExtraGB",
                                 {"subscriberID": _get_sub_id()})
def bonus_data():    return _get("BBVAS/BonusData",
                                 {"subscriberID": _get_sub_id()})


# ---------- normalisation ----------

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _expiry(d):
    ts = d.get("timestamp") or 0
    if ts:
        try:
            return time.strftime("%d-%b %H:%M", time.localtime(ts / 1000))
        except (ValueError, OSError):
            pass
    return d.get("expiry_date")


def _row(name, used, limit, unit="GB", exp=None, kind="other"):
    used, limit = _num(used), _num(limit)
    return {"name": name, "used": used, "limit": limit,
            "remaining": max(limit - used, 0.0),
            "frac": (used / limit) if limit else 0.0,
            "unit": unit or "GB", "expiry": exp, "kind": kind}


def summarise():
    db = usage_summary()
    info = db.get("my_package_info") or {}
    rows = [_row(d.get("name"), d.get("used"), d.get("limit"),
                 d.get("volume_unit"), _expiry(d), "package")
            for d in (info.get("usageDetails") or [])]

    if CFG.SHOW_ADDONS_DETAIL:
        try:
            for d in ((addons() or {}).get("usageDetails") or []):
                rows.append(_row(d.get("name"), d.get("used"), d.get("limit"),
                                 d.get("volume_unit"), _expiry(d), "addon"))
        except SLTError:
            s = db.get("vas_data_summary")
            if s:
                rows.append(_row("Add-Ons Data", s.get("used"), s.get("limit"),
                                 s.get("volume_unit"), None, "addon"))
    else:
        s = db.get("vas_data_summary")
        if s:
            rows.append(_row("Add-Ons Data", s.get("used"), s.get("limit"),
                             s.get("volume_unit"), None, "addon"))

    for key, label in (("extra_gb_data_summary", "Extra GB"),
                       ("bonus_data_summary", "Bonus Data"),
                       ("free_data_summary", "Free Data")):
        s = db.get(key)
        if s:
            rows.append(_row(label, s.get("used"), s.get("limit"),
                             s.get("volume_unit"), None, key))

    return {"package": info.get("package_name") or "",
            "status": db.get("status") or "",
            "reported": db.get("reported_time") or "",
            "rows": rows}


if __name__ == "__main__":
    print(json.dumps(summarise(), indent=2))
