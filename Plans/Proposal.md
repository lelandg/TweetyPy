# TweetyPy – Proposal for a Modern Twitter Thread Composer

## Executive Summary
TweetyPy will be a polished, cross-platform Twitter thread composer built with PySide6 for a native-feeling GUI and a robust CLI for automation. Users can write longform text and post it as a sequence of tweets that respect Twitter’s 280-character limit, automatically adding compact pagination suffixes like " 1/5", " 2/5" to each segment. The app will feature a modern text editor, live tweet-length feedback, a thread preview, secure configuration for Twitter API credentials, and importers that can convert a variety of files to text in CLI mode.

The solution emphasizes solid architecture, testability, secure config handling, and a delightful user experience.

---

## Goals and Non‑Goals
- Goals
  - Native GUI using PySide6 with a responsive layout and system theme support.
  - Rich text editor for composing, with live counters and thread preview.
  - Accurate splitting into tweets while accounting for the pagination suffix length (i/n), ensuring every tweet ≤ 280 chars.
  - Settings dialog to manage Twitter API credentials (OAuth2 Client ID/Secret, or classic API keys where applicable).
  - CLI operation: accept any text-convertible file, split, and post as a thread.
  - Safe config storage (keyring preferred) and graceful fallbacks.
  - Extensible design: importers, validators, and future features.

- Non‑Goals (Phase 1)
  - In-app OAuth web flows (can be added in Phase 2; Phase 1 takes stored credentials/token approach or launches browser as needed).
  - Advanced media handling (images/video) and analytics. These are roadmap items.

---

## User Experience
- Editor & Layout
  - Main window with a large QTextEdit for composing.
  - A right-side panel showing:
    - Live character count for the current draft and the effective limit (280 minus suffix).
    - Estimated number of tweets after splitting.
    - A preview list of the resulting tweets with their suffixes appended (e.g., "Hello world 1/2").
  - Toolbar and menu with actions: New, Open, Save Draft, Import from File, Post, Settings, Help.
  - Keyboard shortcuts (Ctrl+N/O/S/P), and auto-save of the current draft to avoid data loss.
  - Theming: light/dark, or follow system.

- Posting Flow
  1. Compose or import text.
  2. Live preview shows the thread segments.
  3. Click Post → confirmation dialog showing the number of tweets and a quick preview.
  4. Post sequentially; show progress and any errors.

- Settings Dialog
  - Fields for Twitter API credentials: Client ID/Secret (OAuth2), optionally API Key/Secret and Access Token if using Tweepy with OAuth1.0a where permitted.
  - Secure storage via keyring when available; fallback to a local config file.
  - Test Connection button attempts a dry-run auth or capability check.

---

## Thread Splitting Algorithm
Key requirement: Append suffixes " i/n" and ensure each tweet ≤ 280 characters. Because the suffix length depends on n (total number of tweets) and i (current index), we:

1. Normalize whitespace without disrupting content (preserve paragraphs; replace runs of whitespace with single spaces except double newlines for paragraphs).
2. Compute a conservative suffix length using the worst-case digits(n) for both i and n. We reserve: len_suffix = len(f" {n}/{n}") = 1 + digits(n) + 1 + digits(n).
3. Iteratively split until stable:
   - Start with an initial guess for n (e.g., assume 1–9 → digits = 1), compute max_len = 280 - len_suffix.
   - Perform greedy split on word boundaries; if a single word exceeds max_len, hard-split that word.
   - After a pass, set n = number of chunks produced; recompute digits(n), therefore len_suffix, and re-split with the updated max_len.
   - Repeat until the number of chunks stabilizes or a max iteration threshold is reached (it typically stabilizes in 1–2 iterations).
4. Append suffixes " i/n" to each chunk.

This guarantees that every final tweet including its suffix is within the 280-character limit, even when n grows from 9→10, 99→100, etc.

---

## Architecture Overview
- Core Modules
  - config.py (within main.py initially): ConfigManager for reading/storing credentials. Uses keyring when present; otherwise JSON in a config directory (e.g., %APPDATA%/TweetyPy on Windows). Includes schema validation and migration hooks.
  - twitter_client.py (within main.py initially): TwitterClient that posts a thread. Uses Tweepy when installed and configured; otherwise runs in simulate mode printing to console/log.
  - text_splitter.py (within main.py initially): Implements the iterative splitting algorithm described above, with robust handling of long words and Unicode.
  - importers.py (within main.py initially): Simple registry for file importers. Built-in: .txt, .md, .csv, .json, .py (plain text). Optional: .pdf (pdfminer.six), .docx (python-docx), .rtf (strip tags), .html (BeautifulSoup) if available.
  - cli.py (within main.py initially): argparse-based CLI to accept a file path and optional flags to simulate or actually post.
  - gui.py (within main.py initially): PySide6 main window with editor, live counters, preview, post action, and settings dialog.

- Packaging
  - Phase 1: single-file main.py with internal classes for simplicity.
  - Phase 2: refactor into a proper package with modules, tests, and installers (PyInstaller for .exe, Briefcase or MSI packaging for Windows, etc.).

- Logging
  - Python logging module with rotating logs to a user-writable directory. GUI has a simple log viewer in Help → Show Logs.

---

## Security & Privacy
- Use keyring to store secrets in the OS keychain: Windows Credential Manager, macOS Keychain, or Freedesktop Secret Service.
- On fallback to file, restrict permissions and encrypt if a system key is available (roadmap feature). Store only what is necessary, prefer short-lived tokens.
- Never log secrets. Redact sensitive fields in UI and logs.

---

## Dependencies
- Required
  - PySide6 for GUI.

- Optional/Recommended
  - tweepy for Twitter API interactions (OAuth2/OAuth1.0a where permitted).
  - keyring for secure credential storage.
  - chardet for robust file encoding detection.
  - pdfminer.six for PDFs, python-docx for DOCX, beautifulsoup4+lxml for HTML, pypandoc as a general converter (optional).

All optional dependencies are used only if present; otherwise features degrade gracefully.

---

## CLI Design
- Basic usage
  - python main.py --file "path\\to\\input.txt" --simulate
  - python main.py --file "path\\to\\paper.pdf" --post

- Flags
  - --file: input file path to convert to text.
  - --simulate: do not call the API; print what would be posted.
  - --post: actually post (requires configured credentials and tweepy installed).
  - --gui: force opening the GUI instead of CLI processing.
  - --max-tweet-length: defaults to 280; for testing or API changes.

- Output
  - Prints segmented tweets with numbering in simulate mode; returns nonzero exit on failure.

---

## GUI Design Details
- Main Window
  - QTextEdit as the central editor.
  - Status bar with: current chars, reserved suffix length, estimated tweets.
  - A preview dock/panel listing each tweet segment.
  - Actions: New, Open, Save Draft, Import, Post, Settings, Exit. Keyboard shortcuts.

- Settings Dialog
  - Tabs or sections for: API Credentials, Behavior (autosave interval, theme), Advanced (proxies, logging).
  - Validate and save to keyring/JSON on OK.

- Error Handling
  - Non-blocking message banners for minor issues; modal dialogs for critical errors.

---

## Testing Strategy
- Unit tests for:
  - text splitting algorithm (boundary cases; n=9→10, giant words, Unicode/emoji length counting by code points).
  - config manager (read/write, keyring fallback).

- Integration tests (later):
  - Mocked Twitter client posting sequences and error propagation.
  - Importers on sample files.

---

## Roadmap
- Phase 1 (this proposal + initial implementation)
  - Single-file app with GUI, CLI, and simulate-capable posting; basic settings dialog; text importers.
- Phase 2
  - Modularization, tests, packaging, CI, auto-update.
  - OAuth2 authorization flow, token refresh, and secure storage.
  - Media attachments, scheduled posting, draft manager, and templates.
  - Accessibility improvements and localization.

---

## Compliance Notes
- Follow Twitter Developer Agreement and Policy. Avoid storing user data beyond what’s necessary to operate. Offer clear user controls for configuration and logout/revoke.

---

## Conclusion
TweetyPy will provide a modern, reliable way to author long-form text and post it to Twitter as a cleanly paginated thread. With a PySide6 GUI, a capable CLI, secure configuration handling, and a robust splitting algorithm, it balances usability with engineering rigor and a clear path for future enhancements.