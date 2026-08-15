from setuptools import setup

APP = ["mac_widget.py"]
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "LSUIElement": True,
        "CFBundleName": "SLT Data Widget",
        "CFBundleDisplayName": "SLT Data Widget",
        "CFBundleIdentifier": "com.sltwidget.menubar",
        "CFBundleShortVersionString": "1.0.0",
    },
    "packages": ["rumps", "keyring"],
}

setup(
    app=APP,
    name="SLT Data Widget",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
