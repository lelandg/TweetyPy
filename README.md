# TweetyPy

### A cross‑platform Python app to compose long tweets (threads) and help post them to Twitter. 


## Features

- Includes a modern GUI (when PySide6 is installed) and a CLI for automation. 
- Text is split into 280‑character tweets with smart pagination (e.g., " 1/5").
- Compose long text and split into a numbered thread under 280 characters per tweet.
- Live preview (GUI) with per-tweet items.
- Character and tweet counters in the status bar (GUI).
- Post a thread using Twitter API via Tweepy (when configured).
- Simulate mode that logs what would be posted without calling Twitter.
- Import text from many formats (txt, md, csv, json, py; optional: pdf, docx, html).
- Secure-ish credentials: prefers OS keyring; encrypted file fallback.
- Auto-saved draft history; file open/save tracked in recent files.

## Quick Start (Beginners)

If you are new to Python, follow these steps.

1. Install Python
   - Windows:
     - Go to https://www.python.org/downloads/windows/
     - Download the latest Python 3.x installer (64‑bit recommended).
     - Run the installer. IMPORTANT: check "Add Python to PATH" during installation.
   - macOS:
     - Install via Homebrew: `brew install python` (https://brew.sh) or download from https://www.python.org/downloads/macos/
   - Linux:
     - Use your distro’s package manager, e.g. Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y python3 python3-pip`

2. Verify Python and pip
   - Open Terminal (Command Prompt/PowerShell on Windows) and run:
     - `python --version` (or `python3 --version`)
     - `pip --version` (or `pip3 --version`)

3. Download this project
   - If you have Git: `git clone https://github.com/<your-org-or-user>/TweetyPy.git`
   - Or download the ZIP from GitHub and extract it.

4. (Recommended) Create a virtual environment
   - Windows PowerShell:
     - `python -m venv .venv`
     - `.\.venv\Scripts\Activate.ps1`
   - macOS/Linux:
     - `python3 -m venv .venv`
     - `source .venv/bin/activate`

5. Install dependencies
   - Minimum (GUI optional):
     - `pip install -r requirements.txt` (if present)
     - If there is no requirements.txt, install directly:
       - GUI: `pip install PySide6`
       - Posting: `pip install tweepy`
       - Optional helpers: `pip install keyring chardet`
       - Optional importers: `pip install pdfminer.six python-docx beautifulsoup4 lxml`

6. Run TweetyPy
   - GUI (recommended): `python main.py --gui`
   - CLI simulate (no posting): `python main.py --file "path\to\text.txt"`
   - CLI post (actually posts): `python main.py --file "path\to\text.txt" --post`

Tip: Precompiling Python libraries will improve performance, but only for the first time you load a module.

## Requirements

- Python 3.8+ recommended.
- Optional but recommended:
  - PySide6 for GUI
  - tweepy for posting
  - keyring for secure credential storage
  - chardet for robust text encoding detection
  - pdfminer.six, python-docx, beautifulsoup4+lxml for richer imports

All optional dependencies are used only if present; otherwise the app degrades gracefully (e.g., GUI or posting may be unavailable).

## How To Use

### Running the GUI
- Start with `python main.py --gui` (if PySide6 is installed). If not installed, the app runs in simulate/CLI mode.
- Main actions:
  - New, Open, Save Draft, Import from File, Post, Settings, Exit.
  - Keyboard shortcuts: Ctrl+N, Ctrl+O, Ctrl+S, Ctrl+P.
- Right side shows:
  - Preview list of tweets.
  - History panel for auto-saved sessions. Double-click to load.
- Copy-to-clipboard from preview: enable/disable via the checkbox at the top of the preview panel. The preference is saved.
  - Use this to easily copy text and paste directly to Twitter. This does not require an API key. If you have one, you can use it, and it's stored securely.  
- Status bar shows:
  - Character count.
  - Tweet count.
  - Tweet length.
  - Tweet count/length for the current file.
  - Current file path.
  - Recent files.
- Settings panel:
  - Configure credentials.
  - Configure max tweet length.


### Posting a Thread
- Click Post in the GUI or run the CLI with `--post`. This will require your API key and tokens.
- If you don't have an API key, just use the copy/paste feature. That's free!
- If credentials are not configured or Tweepy is missing, the app will simulate and log the output instead of posting. 

### Running via CLI
- Basic examples:
  - Simulate: `python main.py --file "path\to\input.txt"`
  - Post: `python main.py --file "path\to\paper.pdf" --post`
  - Force GUI: `python main.py --gui`
  - Override length (testing): `python main.py --file input.txt --max-tweet-length 280`

Exit codes: 0 success; 1 error during posting; 2 file read error.

## Credentials and Configuration

TweetyPy stores settings in a user directory, typically:
- Windows: `%APPDATA%\TweetyPy`
- Other OS: `~/.config/TweetyPy`

What is stored:
- Non-sensitive settings in `config.json` (e.g., last_file, UI state, recent_files).
- Sensitive credentials in the OS keyring when available (Windows Credential Manager, macOS Keychain, or Secret Service). If unavailable, an encrypted fallback file `secrets.bin` is used (or plain JSON legacy fallback).

Configure credentials from the GUI (Settings) or by programmatically using ConfigManager. Required fields for Tweepy (classic API v1.1):
- API Key
- API Secret Key
- Access Token
- Access Token Secret

Note: Respect Twitter’s Developer Policies and any API limitations in your region or account.

## Drafts, History, and Recent Files

- Auto-save: While composing in the GUI without an explicitly opened/saved file, TweetyPy auto-saves snapshots into `%APPDATA%\TweetyPy\History` (or the platform equivalent). These appear in the History panel; select to preview, double-click to load.
- Explicit files: When you Open or Save, TweetyPy records that path as `last_file` and adds it to `recent_files` in `config.json`. While an explicit file is in use, auto-saving to History is paused to avoid confusion.

## Importing Content

TweetyPy reads plain text directly. For other formats, it attempts to convert to text using optional libraries when available:
- PDF: pdfminer.six
- DOCX: python-docx
- HTML: beautifulsoup4 + lxml
- Fallback: If conversion fails, it reads the file as text using UTF‑8 or a detected encoding (via chardet) where possible.

## How Thread Splitting Works

- Text is split on word boundaries where possible.
- Each tweet receives a compact suffix like " 1/5".
- The algorithm accounts for the suffix length so every tweet including the suffix stays ≤ 280 characters.
- Very long words are hard-split when necessary.

## Tips and Performance

- Tip: Precompiling Python libraries will improve performance, but only for the first time you load a module.
- Use a virtual environment to keep dependencies clean and avoid system conflicts.
- If the GUI does not launch, ensure PySide6 is installed: `pip install PySide6`.
- If posting doesn’t work, ensure Tweepy is installed and credentials are valid: `pip install tweepy`.
- You can run in simulate mode (`--simulate` default) to preview tweets and confirm splitting before posting for real.

## Troubleshooting

- Python not found on Windows: rerun the installer and ensure "Add Python to PATH" is checked, or access Python via the Start Menu > Python.
- Permission errors writing config/logs: Ensure your user has write access to the application data directory listed above.
- Encoding issues: Install `chardet` to improve detection of non‑UTF‑8 files.
- Tweepy errors: Double-check API keys/tokens and network connectivity; consult logs in `%APPDATA%\TweetyPy\logs`.

## Logging

TweetyPy writes rotating logs to a user-writable location (e.g., `%APPDATA%\TweetyPy\logs`). Use logs to diagnose file import or posting problems.

## Security & Privacy

- Secrets are stored in the OS keychain when available. Avoid sharing your `config.json` and `secrets.bin`.
- Do not commit real credentials to Git.
- Logs avoid printing secrets, but you should still review logs before sharing them.

## Contributing

Issues and PRs are welcome. Please discuss large changes in an issue first. For local development, use a virtual environment and ensure linters/tests (if present) pass.

## License

This project is licensed under the terms of the LICENSE file in this repository.
