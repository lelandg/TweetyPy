"""
TweetyPy - GUI and CLI Twitter Thread Composer

Usage examples:
Windows PowerShell:
  python .\main.py --file "C:\\path\\to\\input.txt" --simulate
  python .\main.py --file "C:\\path\\to\\paper.pdf" --post
  python .\main.py --gui (default)

Linux/Mac:
  python ./main.py --file "/path/to/input.txt" --simulate
  python ./main.py --file "/path/to/paper.pdf" --post
  python ./main.py --gui

Notes:
- Default behavior:
    - Opens GUI if PySide6 is available, else runs in simulate mode.
    - If --file is provided, run CLI; otherwise, launch GUI if PySide6 is available.
- Posting requires Tweepy and valid credentials (API Key/Secret and Access Token/Secret).
- If Tweepy or credentials are missing, the app runs in simulate mode.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional, Tuple

# Optional dependencies
try:
    import keyring  # type: ignore
except Exception:  # pragma: no cover - optional
    keyring = None  # type: ignore

try:
    import chardet  # type: ignore
except Exception:  # pragma: no cover - optional
    chardet = None  # type: ignore

try:
    import tweepy  # type: ignore
except Exception:  # pragma: no cover - optional
    tweepy = None  # type: ignore

# GUI (optional)
try:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
except Exception:  # pragma: no cover - optional
    QtCore = QtGui = QtWidgets = None  # type: ignore

APP_NAME = "TweetyPy"
DEFAULT_MAX_TWEET_LEN = 280


def get_app_dir() -> Path:
    # Prefer Windows APPDATA, else fallback to ~/.config/TweetyPy
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home() / ".config"
    app_dir = base / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def setup_logging() -> logging.Logger:
    log_dir = get_app_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{APP_NAME.lower()}.log"

    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = RotatingFileHandler(str(log_file), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    return logger


LOGGER = setup_logging()


class ConfigManager:
    """Manages API credentials with keyring preferred, JSON fallback."""

    SERVICE = APP_NAME
    CONFIG_FILE = get_app_dir() / "config.json"

    # Note: Do not store your keys in this file and then commit it to Git! (Or any repository.)
    SENSITIVE_KEYS = [
        "api_key",
        "api_secret_key",
        "access_token",
        "access_token_secret",
    ]

    @classmethod
    def load(cls) -> dict:
        data: dict = {}
        # Load non-sensitive data from JSON (if any)
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:  # pragma: no cover - corruption is rare
                LOGGER.warning(f"Failed to read config.json: {e}")
                data = {}
        # Load sensitive values
        for key in cls.SENSITIVE_KEYS:
            val = None
            if keyring is not None:
                try:
                    val = keyring.get_password(cls.SERVICE, key)
                except Exception as e:  # pragma: no cover
                    LOGGER.warning(f"Keyring get failed for {key}: {e}")
            if val is None:
                # Fallback from JSON for convenience if present (less secure)
                val = data.get(key)
            if val is not None:
                data[key] = val
        return data

    @classmethod
    def save(cls, values: dict) -> None:
        # Save sensitive values to keyring when possible
        to_file: dict = {}
        for k, v in values.items():
            if k in cls.SENSITIVE_KEYS and keyring is not None:
                try:
                    if v is None or v == "":
                        # Clear stored secret
                        keyring.delete_password(cls.SERVICE, k)  # type: ignore
                    else:
                        keyring.set_password(cls.SERVICE, k, str(v))  # type: ignore
                    continue
                except Exception as e:  # pragma: no cover
                    LOGGER.warning(f"Keyring set failed for {k}: {e}")
            # Fall back to config file
            to_file[k] = v
        # Merge with existing non-sensitive settings in the file
        existing = {}
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}
        existing.update(to_file)
        try:
            with open(cls.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:  # pragma: no cover
            LOGGER.error(f"Failed to write config.json: {e}")

    @classmethod
    def get(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        return cls.load().get(key, default)

    @classmethod
    def set(cls, key: str, value: Optional[str]) -> None:
        data = cls.load()
        data[key] = value
        cls.save(data)


# --------------- Text importers ---------------

def _read_text_file(path: Path) -> str:
    if chardet is not None:
        try:
            raw = path.read_bytes()
            enc = chardet.detect(raw).get("encoding") or "utf-8"
            return raw.decode(enc, errors="replace")
        except Exception:
            return path.read_text(encoding="utf-8", errors="replace")
    else:
        return path.read_text(encoding="utf-8", errors="replace")


def _read_json_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        try:
            data = json.load(f)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            # Fallback: as text
            return _read_text_file(path)


def _read_csv_file(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            output = io.StringIO()
            for row in reader:
                output.write("\t".join(row) + "\n")
            return output.getvalue()
    except Exception:
        return _read_text_file(path)


def _read_pdf_file(path: Path) -> Optional[str]:  # optional
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except Exception:
        return None
    try:
        return extract_text(str(path))
    except Exception:
        return None


def _read_docx_file(path: Path) -> Optional[str]:  # optional
    try:
        import docx  # type: ignore
    except Exception:
        return None
    try:
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return None


def _read_html_file(path: Path) -> Optional[str]:  # optional
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        return None
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml") if "lxml" else BeautifulSoup(html, "html.parser")
        return soup.get_text("\n")
    except Exception:
        return None


def read_file_to_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    ext = path.suffix.lower()
    if ext in (".txt", ".md", ".rst", ".py", ".log"):
        return _read_text_file(path)
    if ext in (".json",):
        return _read_json_file(path)
    if ext in (".csv", ".tsv"):
        return _read_csv_file(path)
    if ext in (".pdf",):
        txt = _read_pdf_file(path)
        if txt is not None:
            return txt
    if ext in (".docx",):
        txt = _read_docx_file(path)
        if txt is not None:
            return txt
    if ext in (".html", ".htm"):
        txt = _read_html_file(path)
        if txt is not None:
            return txt
    # Fallback: read as text
    return _read_text_file(path)


# --------------- Thread splitting ---------------

def digits(n: int) -> int:
    return len(str(abs(n)))


def suffix_length(n_total: int) -> int:
    # Length of " i/n" using worst-case i digits equal to digits(n_total)
    d = digits(n_total)
    return 1 + d + 1 + d  # space + i + slash + n


def greedy_split_within_limit(text: str, limit: int) -> List[str]:
    # Greedily take chunks up to limit, prefer breaking at whitespace.
    chunks: List[str] = []
    i = 0
    N = len(text)
    ws = re.compile(r"\s")
    while i < N:
        end = min(i + limit, N)
        chunk = text[i:end]
        if end < N:
            # try break at last whitespace within chunk
            last_ws = -1
            for m in ws.finditer(chunk):
                last_ws = m.start()
            if last_ws > 0:
                end = i + last_ws
                chunk = text[i:end]
        # strip leading/trailing spaces to avoid awkward boundaries
        cleaned = chunk.strip()
        if cleaned:
            chunks.append(cleaned)
        # advance index; skip any whitespace between chunks
        i = end
        while i < N and text[i].isspace():
            i += 1
        if i == end and end == N and not cleaned:
            break
        # Hard-split for pathological case where no progress
        if i <= end - limit and limit > 0:
            i = end
    return chunks


def split_text_into_tweets(text: str, max_len: int = DEFAULT_MAX_TWEET_LEN) -> List[str]:
    # Normalize newlines; keep other whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.strip()
    if not text:
        return []

    # Initial estimate assumes <= 9 tweets → 1 digit
    n_est = 9
    prev_count = -1
    for _ in range(10):  # should stabilize quickly
        reserved = suffix_length(n_est)
        body_limit = max_len - reserved
        if body_limit <= 0:
            raise ValueError("Max tweet length too small to accommodate suffix")
        bodies = []
        # We need to also deal with single words longer than body_limit: do hard-split
        # Use a pass that prefers whitespace, but if any segment > body_limit without whitespace, hard-split
        tmp_chunks = greedy_split_within_limit(text, body_limit)
        for c in tmp_chunks:
            if len(c) <= body_limit:
                bodies.append(c)
            else:
                # hard split
                start = 0
                while start < len(c):
                    bodies.append(c[start:start + body_limit])
                    start += body_limit
        n_new = len(bodies)
        if n_new == prev_count:
            n_est = n_new
            break
        prev_count = n_new
        # Update estimate to new count; ensures suffix accounts for correct digits
        n_est = max(1, n_new)
        # if digits changed (e.g., 9->10), loop will recompute body_limit and resplit
    # Final suffix append
    n_total = max(1, prev_count)
    reserved = suffix_length(n_total)
    body_limit = max_len - reserved
    final_bodies: List[str] = []
    tmp_chunks = greedy_split_within_limit(text, body_limit)
    for c in tmp_chunks:
        if len(c) <= body_limit:
            final_bodies.append(c)
        else:
            start = 0
            while start < len(c):
                final_bodies.append(c[start:start + body_limit])
                start += body_limit
    n_total = len(final_bodies)
    tweets = [f"{final_bodies[i]} {i+1}/{n_total}" for i in range(n_total)]
    return tweets


# --------------- Twitter Client ---------------

@dataclass
class TwitterCredentials:
    api_key: Optional[str] = None
    api_secret_key: Optional[str] = None
    access_token: Optional[str] = None
    access_token_secret: Optional[str] = None


class TwitterClient:
    def __init__(self, creds: Optional[TwitterCredentials] = None) -> None:
        self.creds = creds or self._load_creds()
        self.available = tweepy is not None and self._creds_complete()
        self.api = None
        if self.available:
            try:
                auth = tweepy.OAuth1UserHandler(
                    self.creds.api_key,
                    self.creds.api_secret_key,
                    self.creds.access_token,
                    self.creds.access_token_secret,
                )
                self.api = tweepy.API(auth)
                # Verify credentials
                self.api.verify_credentials()
                LOGGER.info("Authenticated with Twitter API.")
            except Exception as e:  # pragma: no cover - network dependent
                LOGGER.warning(f"Twitter auth failed: {e}")
                self.available = False
                self.api = None
        else:
            if tweepy is None:
                LOGGER.info("tweepy not installed; running in simulate mode.")
            else:
                LOGGER.info("Incomplete credentials; running in simulate mode.")

    def _creds_complete(self) -> bool:
        c = self.creds
        return bool(c.api_key and c.api_secret_key and c.access_token and c.access_token_secret)

    def _load_creds(self) -> TwitterCredentials:
        data = ConfigManager.load()
        return TwitterCredentials(
            api_key=data.get("api_key"),
            api_secret_key=data.get("api_secret_key"),
            access_token=data.get("access_token"),
            access_token_secret=data.get("access_token_secret"),
        )

    def post_thread(self, tweets: List[str], simulate: bool = False) -> Tuple[bool, Optional[str]]:
        if not tweets:
            return False, "No tweets to post."
        if simulate or not self.available or self.api is None:
            LOGGER.info("Simulate mode: would post thread:")
            for t in tweets:
                LOGGER.info(f"TWEET: {t}")
            return True, None
        try:
            first = self.api.update_status(status=tweets[0])
            last_id = first.id
            LOGGER.info(f"Posted 1/{len(tweets)}: id={last_id}")
            for i, t in enumerate(tweets[1:], start=2):
                status = self.api.update_status(
                    status=t,
                    in_reply_to_status_id=last_id,
                    auto_populate_reply_metadata=True,
                )
                last_id = status.id
                LOGGER.info(f"Posted {i}/{len(tweets)}: id={last_id}")
            return True, None
        except Exception as e:  # pragma: no cover - network dependent
            LOGGER.error(f"Failed to post thread: {e}")
            return False, str(e)


# --------------- CLI ---------------

def run_cli(args: argparse.Namespace) -> int:
    try:
        text = read_file_to_text(args.file)
    except Exception as e:
        LOGGER.error(str(e))
        return 2
    max_len = args.max_tweet_length or DEFAULT_MAX_TWEET_LEN
    tweets = split_text_into_tweets(text, max_len=max_len)
    if not tweets:
        LOGGER.info("No content found to post.")
        return 0
    simulate = not args.post
    client = TwitterClient()
    ok, err = client.post_thread(tweets, simulate=simulate)
    if ok:
        LOGGER.info("Done.")
        return 0
    else:
        LOGGER.error(f"Error: {err}")
        return 1


# --------------- GUI ---------------

if QtWidgets:

    class SettingsDialog(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Settings - TweetyPy")
            self.setModal(True)
            layout = QtWidgets.QVBoxLayout(self)

            form = QtWidgets.QFormLayout()
            self.api_key = QtWidgets.QLineEdit()
            self.api_secret = QtWidgets.QLineEdit()
            self.api_secret.setEchoMode(QtWidgets.QLineEdit.Password)
            self.access_token = QtWidgets.QLineEdit()
            self.access_secret = QtWidgets.QLineEdit()
            self.access_secret.setEchoMode(QtWidgets.QLineEdit.Password)

            data = ConfigManager.load()
            self.api_key.setText(data.get("api_key", ""))
            self.api_secret.setText(data.get("api_secret_key", ""))
            self.access_token.setText(data.get("access_token", ""))
            self.access_secret.setText(data.get("access_token_secret", ""))

            form.addRow("API Key:", self.api_key)
            form.addRow("API Secret Key:", self.api_secret)
            form.addRow("Access Token:", self.access_token)
            form.addRow("Access Token Secret:", self.access_secret)

            layout.addLayout(form)

            btns = QtWidgets.QHBoxLayout()
            self.test_btn = QtWidgets.QPushButton("Test Connection")
            self.save_btn = QtWidgets.QPushButton("Save")
            self.cancel_btn = QtWidgets.QPushButton("Cancel")
            btns.addStretch(1)
            btns.addWidget(self.test_btn)
            btns.addWidget(self.save_btn)
            btns.addWidget(self.cancel_btn)
            layout.addLayout(btns)

            self.test_btn.clicked.connect(self.on_test)
            self.save_btn.clicked.connect(self.on_save)
            self.cancel_btn.clicked.connect(self.reject)

        def on_test(self):
            values = {
                "api_key": self.api_key.text().strip(),
                "api_secret_key": self.api_secret.text().strip(),
                "access_token": self.access_token.text().strip(),
                "access_token_secret": self.access_secret.text().strip(),
            }
            temp_creds = TwitterCredentials(
                api_key=values["api_key"],
                api_secret_key=values["api_secret_key"],
                access_token=values["access_token"],
                access_token_secret=values["access_token_secret"],
            )
            client = TwitterClient(temp_creds)
            if client.available:
                QtWidgets.QMessageBox.information(self, "Connection", "Authentication successful.")
            else:
                QtWidgets.QMessageBox.warning(self, "Connection", "Authentication failed or Tweepy not available.")

        def on_save(self):
            values = {
                "api_key": self.api_key.text().strip(),
                "api_secret_key": self.api_secret.text().strip(),
                "access_token": self.access_token.text().strip(),
                "access_token_secret": self.access_secret.text().strip(),
            }
            ConfigManager.save(values)
            QtWidgets.QMessageBox.information(self, "Settings", "Saved.")
            self.accept()


    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("TweetyPy - Thread Composer")
            self.resize(1000, 700)

            # Central editor
            self.editor = QtWidgets.QTextEdit()
            self.editor.setPlaceholderText("Write your thread here…")
            font = QtGui.QFont("Consolas")
            font.setPointSize(11)
            self.editor.setFont(font)
            self.setCentralWidget(self.editor)

            # Preview panel
            self.preview = QtWidgets.QListWidget()
            self.preview.setMinimumWidth(350)
            dock = QtWidgets.QDockWidget("Preview", self)
            dock.setWidget(self.preview)
            self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

            # Status bar labels
            self.status_chars = QtWidgets.QLabel("Chars: 0")
            self.status_est = QtWidgets.QLabel("Tweets: 0")
            self.status_limit = QtWidgets.QLabel(f"Max: {DEFAULT_MAX_TWEET_LEN}")
            self.statusBar().addPermanentWidget(self.status_chars)
            self.statusBar().addPermanentWidget(self.status_est)
            self.statusBar().addPermanentWidget(self.status_limit)

            # Actions
            self._build_actions()
            self._build_menu()
            self._build_toolbar()

            # Signals
            self.editor.textChanged.connect(self.update_preview)

            # Initial preview
            self.update_preview()

        def _build_actions(self):
            self.act_new = QtGui.QAction("New", self)
            self.act_open = QtGui.QAction("Open…", self)
            self.act_save = QtGui.QAction("Save Draft…", self)
            self.act_import = QtGui.QAction("Import from File…", self)
            self.act_post = QtGui.QAction("Post", self)
            self.act_settings = QtGui.QAction("Settings", self)
            self.act_exit = QtGui.QAction("Exit", self)

            self.act_new.setShortcut("Ctrl+N")
            self.act_open.setShortcut("Ctrl+O")
            self.act_save.setShortcut("Ctrl+S")
            self.act_post.setShortcut("Ctrl+P")

            self.act_new.triggered.connect(self.on_new)
            self.act_open.triggered.connect(self.on_open)
            self.act_save.triggered.connect(self.on_save)
            self.act_import.triggered.connect(self.on_import)
            self.act_post.triggered.connect(self.on_post)
            self.act_settings.triggered.connect(self.on_settings)
            self.act_exit.triggered.connect(self.close)

        def _build_menu(self):
            m_file = self.menuBar().addMenu("&File")
            m_file.addAction(self.act_new)
            m_file.addAction(self.act_open)
            m_file.addAction(self.act_save)
            m_file.addSeparator()
            m_file.addAction(self.act_import)
            m_file.addSeparator()
            m_file.addAction(self.act_exit)

            m_tools = self.menuBar().addMenu("&Tools")
            m_tools.addAction(self.act_settings)

            m_post = self.menuBar().addMenu("&Post")
            m_post.addAction(self.act_post)

        def _build_toolbar(self):
            tb = self.addToolBar("Main")
            tb.addAction(self.act_new)
            tb.addAction(self.act_open)
            tb.addAction(self.act_save)
            tb.addAction(self.act_import)
            tb.addSeparator()
            tb.addAction(self.act_post)
            tb.addSeparator()
            tb.addAction(self.act_settings)

        def update_preview(self):
            text = self.editor.toPlainText()
            tweets = split_text_into_tweets(text) if text.strip() else []
            self.preview.clear()
            for t in tweets:
                item = QtWidgets.QListWidgetItem(t)
                self.preview.addItem(item)
            # Update status
            self.status_chars.setText(f"Chars: {len(text)}")
            self.status_est.setText(f"Tweets: {len(tweets)}")

        def on_new(self):
            if self._confirm_discard():
                self.editor.clear()

        def on_open(self):
            file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Draft", str(Path.home()), "Text Files (*.txt *.md *.rst *.log *.json *.csv *.tsv *.py *.pdf *.docx *.html);;All Files (*)")
            if file:
                try:
                    txt = read_file_to_text(file)
                    self.editor.setPlainText(txt)
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Open", str(e))

        def on_save(self):
            file, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Draft", str(Path.home()), "Text Files (*.txt);;All Files (*)")
            if file:
                try:
                    Path(file).write_text(self.editor.toPlainText(), encoding="utf-8")
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Save", str(e))

        def on_import(self):
            self.on_open()

        def on_post(self):
            text = self.editor.toPlainText().strip()
            if not text:
                QtWidgets.QMessageBox.information(self, "Post", "Nothing to post.")
                return
            tweets = split_text_into_tweets(text)
            preview = "\n\n".join(tweets[:5]) + ("\n\n…" if len(tweets) > 5 else "")
            ret = QtWidgets.QMessageBox.question(self, "Confirm Post", f"Post {len(tweets)} tweets as a thread?\n\nPreview:\n\n{preview}")
            if ret != QtWidgets.QMessageBox.Yes:
                return
            client = TwitterClient()
            simulate = not client.available
            ok, err = client.post_thread(tweets, simulate=simulate)
            if ok:
                QtWidgets.QMessageBox.information(self, "Post", "Thread posted successfully." if not simulate else "Simulated posting complete.")
            else:
                QtWidgets.QMessageBox.critical(self, "Post", f"Failed: {err}")

        def on_settings(self):
            dlg = SettingsDialog(self)
            dlg.exec()

        def _confirm_discard(self) -> bool:
            if not self.editor.toPlainText().strip():
                return True
            ret = QtWidgets.QMessageBox.question(self, "Discard", "Discard current draft?")
            return ret == QtWidgets.QMessageBox.Yes


# --------------- Entry Point ---------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="TweetyPy - Compose and post Twitter threads from GUI or CLI.")
    p.add_argument("--file", dest="file", help="Path to input file to convert to text.")
    p.add_argument("--simulate", dest="post", action="store_false", help="Simulate posting (default).")
    p.add_argument("--post", dest="post", action="store_true", help="Actually post the thread (requires credentials and tweepy).")
    p.add_argument("--gui", dest="gui", action="store_true", help="Launch GUI explicitly.")
    p.add_argument("--max-tweet-length", dest="max_tweet_length", type=int, default=DEFAULT_MAX_TWEET_LEN, help="Max tweet length (default 280).")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # If --gui or no --file provided, try GUI
    if args.gui or not args.file:
        if QtWidgets is None:
            LOGGER.error("PySide6 is not installed. Install PySide6 or run with --file for CLI mode.")
            return 3
        app = QtWidgets.QApplication(sys.argv)
        win = MainWindow()
        win.show()
        return app.exec()

    # CLI mode
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
