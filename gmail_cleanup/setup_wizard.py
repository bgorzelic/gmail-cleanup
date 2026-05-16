"""Interactive OAuth setup wizard.

Honest scope: delegated automation, ~80% friction reduction.
Opens browser tabs, polls ~/Downloads, runs OAuth smoke test, writes config.
"""

from __future__ import annotations

import shutil
import time
import webbrowser
from pathlib import Path
from typing import Optional

CREDS_DEST = Path.home() / '.gmail_cli' / 'credentials.json'
DOWNLOADS = Path.home() / 'Downloads'

GCP_PROJECT_CREATE = "https://console.cloud.google.com/projectcreate"
GMAIL_API_LIBRARY = "https://console.cloud.google.com/apis/library/gmail.googleapis.com"
OAUTH_CREDENTIALS = "https://console.cloud.google.com/apis/credentials/oauthclient"


def _press_enter(prompt: str = "Press Enter when done...") -> None:
    input(f"\n  {prompt}\n")


def _open_browser(url: str) -> None:
    print(f"  → opening {url}")
    webbrowser.open(url)


def _find_recent_download(window_secs: int = 300) -> Optional[Path]:
    if not DOWNLOADS.exists():
        return None
    now = time.time()
    candidates = [
        p
        for p in DOWNLOADS.glob('client_secret_*.json')
        if now - p.stat().st_mtime < window_secs
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def run_wizard() -> None:
    print("🧙 gmail-cleanup setup wizard")
    print("=" * 60)
    print("Walks through 6 short steps. Total: ~3 minutes.\n")

    if CREDS_DEST.exists():
        resp = (
            input(
                f"  ⚠️  Credentials exist at {CREDS_DEST}. Overwrite? [y/N] "
            )
            .strip()
            .lower()
        )
        if resp != 'y':
            print("Aborted.")
            return

    print("\n[Step 1/6] Create a Google Cloud project")
    print("  Name it anything (e.g. 'gmail-cleanup'). Click Create.")
    _open_browser(GCP_PROJECT_CREATE)
    _press_enter()

    print("\n[Step 2/6] Enable the Gmail API")
    print("  Click Enable.")
    _open_browser(GMAIL_API_LIBRARY)
    _press_enter()

    print(
        "\n[Step 3/6] Create an OAuth Desktop Application client"
    )
    print(
        "  Application type: 'Desktop app'. Name it anything. Click Create."
    )
    print("  When the modal appears, click 'Download JSON'.")
    _open_browser(OAUTH_CREDENTIALS)
    _press_enter()

    print("\n[Step 4/6] Locate the downloaded credentials file")
    downloaded = _find_recent_download()
    if downloaded:
        resp = (
            input(
                f"  Found: {downloaded}\n  Move to {CREDS_DEST}? [Y/n] "
            )
            .strip()
            .lower()
        )
        if resp in ('', 'y'):
            CREDS_DEST.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(downloaded), str(CREDS_DEST))
            print(f"  ✅ Saved to {CREDS_DEST}")
        else:
            return
    else:
        path_str = input(
            f"  Couldn't find creds in {DOWNLOADS}. Enter path manually: "
        ).strip()
        path = Path(path_str).expanduser()
        if not path.is_file():
            print(f"❌ {path} not found.")
            return
        CREDS_DEST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(path), str(CREDS_DEST))
        print(f"  ✅ Copied to {CREDS_DEST}")

    print("\n[Step 5/6] OAuth smoke test")
    email = input(
        "  Enter the Gmail address you'll authorize as: "
    ).strip()
    if not email:
        print("Aborted.")
        return
    try:
        from gmail_cleanup import GmailCLI

        GmailCLI(email)
        print(f"  ✅ Authorized as {email}")
    except Exception as e:
        print(f"❌ Smoke test failed: {e}")
        return

    print("\n[Step 6/6] Register account in config")
    resp = (
        input(
            f"  Register {email} as default and in accounts list? [Y/n] "
        )
        .strip()
        .lower()
    )
    if resp in ('', 'y'):
        import yaml

        from gmail_cleanup.accounts import add_account
        from gmail_cleanup.config import find_config_file, init_config

        if not find_config_file():
            init_config()
        add_account(email, label='personal')
        path = find_config_file()
        data = yaml.safe_load(path.read_text()) or {}
        data['default_email'] = email
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
        )
        print(f"  ✅ Config updated.")

    print(f"\n🎉 Setup complete! Try: gmail-cleanup stats")
