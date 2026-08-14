# SLT Data Widget (Third-party tool)

> **Note**: This is my personal project. I do not collect any of your data, and the software is completely open source. If you want, you can inspect the code and package your own widget directly from the source! Not officially affiliated with any specific telecom provider.

A compact, highly customizable, and privacy-focused Windows desktop widget for monitoring your SLT (Sri Lanka Telecom) Broadband data usage.

## Features
- **Real-Time Data Monitoring**: Instantly view the status of your Main Package, Add-Ons, Extra GB, Bonus Data, and Free Data.
- **Privacy Mode**: A dedicated "Hide details" toggle that masks all textual usage metrics and numbers so others cannot peek at your screen.
- **Smart Push Notifications**: Hooks directly into the native Windows Toast Notification center. Get alerted when your Main Package balance falls below a customized configurable threshold (e.g., `< 5.0 GB`).
- **Autostart Support**: Optionally configure the widget to launch completely silently via the Windows Registry whenever you boot your PC.
- **No API Keys Needed**: The application's backend automatically fetches the required IBM API Client IDs perfectly on the fly!
- **Data Security guaranteed**: All of your credentials and passwords are 100% stored strictly on your local PC via `settings.json` and the secure OS `keyring`. We do not collect *any* data.

## Setup Instructions

### Getting Started (Executable)
The easiest way to use the widget is to run the standalone executable.
1. Download the compiled `SLT Data Widget.exe`.
2. Double click the file. The widget will force open a **Settings** wizard.
3. Provide your standard MySLT Email, Password, and your landline number (e.g. `011XXXXXXX`).
4. Click **Save & Login**. The background sync will immediately start!

### Building from Source
If you are a developer looking to build the widget yourself:
1. Clone the repository and install the standard `tkinter`, `keyring`, and `win10toast` library requirements.
2. Run the `slt_widget.pyw` module to launch the Python UI instance.
3. You can optionally package it using Pyinstaller:
```bash
pip install pyinstaller
pyinstaller --noconsole --name "SLT Data Widget" --onefile slt_widget.pyw
```

## Legal Disclaimer
This is a 100% unofficial, community-driven, third-party open-source project. **This software is NOT affiliated, endorsed, authorized, or partnered with Sri Lanka Telecom PLC (SLT) in any capacity.** 

This software solely acts as a local UI wrapper to interface with the public APIs strictly on behalf of the end-user. It does not circumvent billing mechanisms, DRM, or access control. All trademarks and copyrights belong to their respective corporate owners. Use of this software is entirely at your own risk per the MIT License.
