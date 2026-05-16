#!/usr/bin/env python3
"""
Gmail Cleanup CLI Tool

A powerful command-line tool for cleaning up and organizing Gmail.
Uses OAuth credentials to access Gmail API directly.
"""

import os
import re
import sys
import json
import base64
import urllib.parse
import urllib.request
import urllib.error
from email.message import EmailMessage
import pickle
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta

import yaml

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# OAuth scopes needed for Gmail operations
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.settings.basic',
]

# HTTP request settings for unsubscribe link execution
UNSUB_HTTP_TIMEOUT = 5  # seconds
UNSUB_USER_AGENT = 'Mozilla/5.0 (compatible; gmail-cli-unsubscribe/1.0)'

# Configurable lists live in lists/*.yaml. Users edit them without touching code.
LISTS_DIR = Path(__file__).parent.parent / 'lists'


def _load_list(name: str) -> List[str]:
    """Load a YAML list file from lists/. Returns [] if missing.

    Raises ValueError if the file exists but isn't a top-level YAML list.
    """
    path = LISTS_DIR / f'{name}.yaml'
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f) or []
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a top-level YAML list (got {type(data).__name__})")
    return [str(x).strip() for x in data if x and str(x).strip()]


VETTED_KILL_LIST = _load_list('kill')
UNSUB_KEEP_LIST = _load_list('keep')
HUMANS_WHITELIST = _load_list('humans')
UNSUBBED_SENDERS = _load_list('unsubbed')

# Credentials directory
CREDS_DIR = Path.home() / '.gmail_cli'
LEGACY_TOKEN_FILE = CREDS_DIR / 'token.pickle'


def _credentials_search_paths() -> List[Path]:
    """Return the ordered list of paths where we look for credentials.json.

    First match wins. Order:
      1. $GMAIL_CLEANUP_CREDENTIALS env var (explicit path override)
      2. ~/.gmail_cli/credentials.json (canonical per-user location)
      3. ./credentials.json (current working directory — dev/repo convenience)
      4. <package dir>/credentials.json (legacy — for running from a clone)
    """
    paths = []
    env_path = os.getenv('GMAIL_CLEANUP_CREDENTIALS')
    if env_path:
        paths.append(Path(env_path).expanduser())
    paths.append(CREDS_DIR / 'credentials.json')
    paths.append(Path.cwd() / 'credentials.json')
    paths.append(Path(__file__).parent / 'credentials.json')
    return paths


def _find_credentials_file() -> Optional[Path]:
    """Walk the search paths and return the first credentials.json that exists."""
    for p in _credentials_search_paths():
        if p.is_file():
            return p
    return None


def _token_path(user_email: str) -> Path:
    """Per-account token file. Sanitize email for filesystem."""
    safe = user_email.replace('/', '_').replace('\\', '_')
    return CREDS_DIR / f'token_{safe}.pickle'


class GmailCLI:
    """Gmail API wrapper for CLI operations"""

    def __init__(self, user_email: str):
        self.user_email = user_email
        self.token_file = _token_path(user_email)
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth"""
        creds = None

        # Check if we have saved credentials for this account
        if self.token_file.exists():
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        # If credentials are invalid or don't exist, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing access token...")
                creds.refresh(Request())
            else:
                # Search for credentials.json in standard locations (in order of preference).
                creds_file = _find_credentials_file()
                if creds_file:
                    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
                else:
                    client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
                    client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

                    if not client_id or not client_secret:
                        print("❌ Could not find OAuth credentials.\n")
                        print("Checked these locations for credentials.json:")
                        for p in _credentials_search_paths():
                            print(f"  • {p}")
                        print()
                        print("To get started:")
                        print(f"  1. Visit https://console.cloud.google.com/apis/credentials")
                        print(f"     and create an OAuth 2.0 Client ID of type 'Desktop app'.")
                        print(f"  2. Download the JSON and save it as:")
                        print(f"     {CREDS_DIR / 'credentials.json'}")
                        print(f"  3. Re-run this command.")
                        print()
                        print("Or set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET env vars.")
                        sys.exit(1)

                    client_config = {
                        "installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "redirect_uris": ["http://localhost:8080/", "urn:ietf:wg:oauth:2.0:oob"]
                        }
                    }
                    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

                print("\nStarting OAuth authorization flow...")
                print("A browser window will open for you to authorize access.")
                creds = flow.run_local_server(port=0)

            # Save credentials for next time
            CREDS_DIR.mkdir(exist_ok=True)
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
            print(f"✅ Credentials saved to {self.token_file.name}\n")

        # Build Gmail service
        self.service = build('gmail', 'v1', credentials=creds)
        print(f"✅ Authenticated as {self.user_email}\n")

    def get_labels(self) -> List[Dict[str, Any]]:
        """Get all Gmail labels"""
        try:
            results = self.service.users().labels().list(userId='me').execute()
            return results.get('labels', [])
        except HttpError as error:
            print(f"❌ Error fetching labels: {error}")
            return []

    def search_messages(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """Search for messages matching query"""
        try:
            messages = []
            request = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=min(max_results, 500)
            )

            while request and len(messages) < max_results:
                response = request.execute()
                messages.extend(response.get('messages', []))
                request = self.service.users().messages().list_next(request, response)

                if not request or len(messages) >= max_results:
                    break

            return messages[:max_results]
        except HttpError as error:
            print(f"❌ Error searching messages: {error}")
            return []

    def get_message(self, message_id: str, format: str = 'full') -> Optional[Dict[str, Any]]:
        """Get a specific message"""
        try:
            return self.service.users().messages().get(
                userId='me',
                id=message_id,
                format=format
            ).execute()
        except HttpError as error:
            print(f"❌ Error fetching message {message_id}: {error}")
            return None

    def get_header(self, message: Dict[str, Any], header_name: str) -> str:
        """Extract header value from message"""
        headers = message.get('payload', {}).get('headers', [])
        for header in headers:
            if header['name'].lower() == header_name.lower():
                return header['value']
        return ''

    def modify_message(self, message_id: str, add_labels: List[str] = None,
                      remove_labels: List[str] = None):
        """Modify message labels"""
        try:
            body = {}
            if add_labels:
                body['addLabelIds'] = add_labels
            if remove_labels:
                body['removeLabelIds'] = remove_labels

            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body=body
            ).execute()
        except HttpError as error:
            print(f"❌ Error modifying message {message_id}: {error}")

    def batch_modify_messages(self, message_ids: List[str], add_labels: List[str] = None,
                             remove_labels: List[str] = None):
        """Batch modify message labels"""
        try:
            body = {'ids': message_ids}
            if add_labels:
                body['addLabelIds'] = add_labels
            if remove_labels:
                body['removeLabelIds'] = remove_labels

            self.service.users().messages().batchModify(
                userId='me',
                body=body
            ).execute()
        except HttpError as error:
            print(f"❌ Error batch modifying messages: {error}")

    def send_message(self, to: str, subject: str = '', body: str = '') -> bool:
        """Send a minimal email (used for mailto: unsubscribe requests)."""
        try:
            msg = EmailMessage()
            msg['To'] = to
            msg['From'] = self.user_email
            if subject:
                msg['Subject'] = subject
            msg.set_content(body or ' ')
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            self.service.users().messages().send(
                userId='me', body={'raw': raw}
            ).execute()
            return True
        except HttpError as error:
            print(f"❌ Error sending unsubscribe email to {to}: {error}")
            return False

    def create_label(self, label_name: str) -> Optional[str]:
        """Create a new label and return its ID"""
        try:
            label = self.service.users().labels().create(
                userId='me',
                body={'name': label_name}
            ).execute()
            return label['id']
        except HttpError as error:
            if 'Label name exists' in str(error):
                # Label already exists, find it
                labels = self.get_labels()
                for label in labels:
                    if label['name'] == label_name:
                        return label['id']
            print(f"❌ Error creating label: {error}")
            return None


def cmd_stats(args):
    """Show inbox statistics"""
    gmail = GmailCLI(args.email)

    print("📊 Gmail Statistics\n")
    print("=" * 60)

    # Inbox count
    inbox_msgs = gmail.search_messages('in:inbox', max_results=10000)
    print(f"📥 Total Inbox Emails: {len(inbox_msgs):,}")

    # Unread count
    unread_msgs = gmail.search_messages('is:unread', max_results=10000)
    print(f"✉️  Unread Emails: {len(unread_msgs):,}")

    # Storage (approximate from message count)
    print(f"💾 Approximate Storage: ~{len(inbox_msgs) * 0.05:.1f} MB")

    # Oldest email in inbox
    if inbox_msgs:
        oldest = gmail.get_message(inbox_msgs[-1]['id'], format='metadata')
        if oldest:
            date = gmail.get_header(oldest, 'Date')
            print(f"📅 Oldest Inbox Email: {date}")

    print("=" * 60)


def cmd_top_senders(args):
    """Find top email senders"""
    gmail = GmailCLI(args.email)

    print(f"🔍 Finding top {args.count} senders from last {args.days} days...\n")

    # Calculate date filter
    date_ago = datetime.now() - timedelta(days=args.days)
    date_str = date_ago.strftime('%Y/%m/%d')

    query = f'after:{date_str}'
    if args.unread:
        query += ' is:unread'

    messages = gmail.search_messages(query, max_results=args.limit)
    print(f"Analyzing {len(messages):,} messages...")

    # Count senders
    sender_counts = defaultdict(int)
    for i, msg in enumerate(messages):
        if i % 100 == 0:
            print(f"Progress: {i}/{len(messages)}", end='\r')

        full_msg = gmail.get_message(msg['id'], format='metadata')
        if full_msg:
            sender = gmail.get_header(full_msg, 'From')
            # Extract email from "Name <email@domain.com>" format
            if '<' in sender:
                sender = sender.split('<')[1].rstrip('>')
            sender_counts[sender] += 1

    print("\n")
    print("=" * 80)
    print(f"{'Rank':<6} {'Count':<8} {'Email':<50}")
    print("=" * 80)

    for rank, (sender, count) in enumerate(
        sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:args.count],
        start=1
    ):
        print(f"{rank:<6} {count:<8} {sender:<50}")

    print("=" * 80)


def cmd_find_subscriptions(args):
    """Find email subscriptions with unsubscribe links"""
    gmail = GmailCLI(args.email)

    print(f"🔍 Finding subscriptions from last {args.days} days...\n")

    # Calculate date filter
    date_ago = datetime.now() - timedelta(days=args.days)
    date_str = date_ago.strftime('%Y/%m/%d')

    # Search for emails with unsubscribe
    query = f'after:{date_str} unsubscribe'
    if args.unread:
        query += ' is:unread'

    messages = gmail.search_messages(query, max_results=args.limit)
    print(f"Found {len(messages):,} emails with 'unsubscribe'")
    print("Analyzing senders...\n")

    # Count by sender
    sender_counts = defaultdict(list)
    for i, msg in enumerate(messages):
        if i % 100 == 0:
            print(f"Progress: {i}/{len(messages)}", end='\r')

        full_msg = gmail.get_message(msg['id'], format='metadata')
        if full_msg:
            sender = gmail.get_header(full_msg, 'From')
            if '<' in sender:
                email = sender.split('<')[1].rstrip('>')
            else:
                email = sender
            sender_counts[email].append(msg['id'])

    print("\n")
    print("=" * 90)
    print(f"{'Rank':<6} {'Count':<8} {'Sender':<50} {'Action':<20}")
    print("=" * 90)

    for rank, (sender, msg_ids) in enumerate(
        sorted(sender_counts.items(), key=lambda x: len(x[1]), reverse=True)[:args.count],
        start=1
    ):
        if len(msg_ids) >= args.min_count:
            action = f"→ Can unsubscribe"
            print(f"{rank:<6} {len(msg_ids):<8} {sender:<50} {action:<20}")

    print("=" * 90)
    print(f"\n💡 Tip: Use 'gmail-cli archive --sender <email>' to clean up after unsubscribing")


def _extract_email(from_header: str) -> str:
    """Pull the bare email address out of a 'Name <email>' header value."""
    if '<' in from_header and '>' in from_header:
        return from_header.split('<', 1)[1].split('>', 1)[0].strip().lower()
    return from_header.strip().lower()


def _parse_list_unsubscribe(header_value: str) -> List[Tuple[str, str]]:
    """Parse a List-Unsubscribe header into [(method, target), ...].

    Methods: 'https' (POST or GET URL) or 'mailto'.
    """
    targets = []
    for match in re.findall(r'<([^>]+)>', header_value or ''):
        target = match.strip()
        if target.lower().startswith('mailto:'):
            targets.append(('mailto', target[7:]))
        elif target.lower().startswith(('http://', 'https://')):
            targets.append(('https', target))
    return targets


def _execute_unsubscribe(
    gmail: 'GmailCLI',
    targets: List[Tuple[str, str]],
    one_click: bool,
) -> Tuple[bool, str]:
    """Try each target in priority order. Returns (success, method_used)."""
    # Priority 1: One-click POST (RFC 8058) — most reliable.
    if one_click:
        for method, target in targets:
            if method == 'https':
                try:
                    data = urllib.parse.urlencode(
                        {'List-Unsubscribe': 'One-Click'}
                    ).encode()
                    req = urllib.request.Request(
                        target, data=data, method='POST',
                        headers={
                            'User-Agent': UNSUB_USER_AGENT,
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                    )
                    with urllib.request.urlopen(req, timeout=UNSUB_HTTP_TIMEOUT) as resp:
                        if 200 <= resp.status < 400:
                            return True, 'POST'
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError):
                    pass
                except Exception:
                    pass

    # Priority 2: HTTPS GET.
    for method, target in targets:
        if method == 'https':
            try:
                req = urllib.request.Request(
                    target, headers={'User-Agent': UNSUB_USER_AGENT}
                )
                with urllib.request.urlopen(req, timeout=UNSUB_HTTP_TIMEOUT) as resp:
                    if 200 <= resp.status < 400:
                        return True, 'GET'
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError):
                continue
            except Exception:
                continue

    # Priority 3: mailto.
    for method, target in targets:
        if method == 'mailto':
            # Strip any ?subject=...&body=... query, use simple unsubscribe message.
            address = target.split('?', 1)[0]
            if gmail.send_message(address, subject='unsubscribe', body='unsubscribe'):
                return True, 'mailto'

    return False, 'none'


def cmd_unsubscribe(args):
    """Find subscription senders and execute List-Unsubscribe actions."""
    gmail = GmailCLI(args.email)

    date_ago = datetime.now() - timedelta(days=args.days)
    date_str = date_ago.strftime('%Y/%m/%d')
    query = f'in:inbox after:{date_str}'

    print(f"🔍 Scanning inbox for subscription senders (last {args.days} days)...")
    messages = gmail.search_messages(query, max_results=args.limit)
    print(f"   Found {len(messages):,} messages to analyze\n")

    # Group by sender. Track one representative message per sender (most recent first
    # is what list() returns).
    sender_msgs: Dict[str, List[str]] = defaultdict(list)
    sender_first_msg: Dict[str, str] = {}

    for i, msg in enumerate(messages):
        if i % 50 == 0:
            print(f"   Analyzing: {i}/{len(messages)}", end='\r')
        full_msg = gmail.get_message(msg['id'], format='metadata')
        if not full_msg:
            continue
        sender = _extract_email(gmail.get_header(full_msg, 'From'))
        if not sender:
            continue
        sender_msgs[sender].append(msg['id'])
        if sender not in sender_first_msg:
            sender_first_msg[sender] = msg['id']

    print(f"   Analyzed {len(messages):,} messages, {len(sender_msgs)} unique senders\n")

    # Build target set: auto-discovery (>= min_count) ∪ kill-list matches,
    # MINUS anything matching the KEEP list (financial / healthcare / etc.).
    targets_to_process = []  # list of (sender, count, list_unsub_header, list_unsub_post_header)
    keep_skipped = []  # senders excluded by the KEEP list, for reporting
    for sender, msg_ids in sender_msgs.items():
        in_killlist = any(killed in sender for killed in VETTED_KILL_LIST)
        meets_threshold = len(msg_ids) >= args.min_count
        if not (in_killlist or meets_threshold):
            continue

        # Safety guard: skip anything matching the KEEP list. Kill-list explicit
        # entries override KEEP (you specifically vetted those).
        if not in_killlist:
            keep_hit = next((k for k in UNSUB_KEEP_LIST if k in sender), None)
            if keep_hit:
                keep_skipped.append((sender, len(msg_ids), keep_hit))
                continue

        # Fetch headers to find List-Unsubscribe.
        rep = gmail.get_message(sender_first_msg[sender], format='metadata')
        if not rep:
            continue
        list_unsub = gmail.get_header(rep, 'List-Unsubscribe')
        if not list_unsub and not in_killlist:
            # No unsubscribe header and not on the vetted kill list — most likely
            # a person, not a service. Skip entirely (don't auto-archive humans).
            continue
        list_unsub_post = gmail.get_header(rep, 'List-Unsubscribe-Post') if list_unsub else ''
        targets_to_process.append((sender, len(msg_ids), list_unsub, list_unsub_post, in_killlist))

    # Sort by message count, descending.
    targets_to_process.sort(key=lambda t: t[1], reverse=True)

    if keep_skipped:
        print(f"🛡  Protected by KEEP list ({len(keep_skipped)} senders skipped):")
        for sender, count, rule in sorted(keep_skipped, key=lambda t: t[1], reverse=True):
            print(f"     {count:>4}  {sender:<50}  [matched '{rule}']")
        print()

    if not targets_to_process:
        print("✅ No subscription senders matched criteria (after KEEP filter)")
        return

    # Preview table.
    print("=" * 100)
    print(f"{'#':<4} {'Count':<7} {'Sender':<45} {'Source':<10} {'Method':<12}")
    print("=" * 100)
    for idx, (sender, count, lu, lup, in_kl) in enumerate(targets_to_process, 1):
        parsed = _parse_list_unsubscribe(lu)
        if not parsed:
            method = 'archive-only'
        elif lup and 'one-click' in lup.lower():
            method = 'POST'
        elif any(m == 'https' for m, _ in parsed):
            method = 'GET'
        else:
            method = 'mailto'
        source = 'killlist' if in_kl else 'auto'
        print(f"{idx:<4} {count:<7} {sender[:43]:<45} {source:<10} {method:<12}")
    print("=" * 100)
    print(f"\nTotal: {len(targets_to_process)} senders, "
          f"{sum(t[1] for t in targets_to_process):,} inbox messages\n")

    if args.dry_run:
        print("🔍 Dry run — no actions taken. Remove --dry-run to execute.")
        return

    # Execute.
    results = {'unsubscribed': 0, 'failed': 0, 'archive_only': 0, 'archived': 0}
    for idx, (sender, count, lu, lup, in_kl) in enumerate(targets_to_process, 1):
        print(f"[{idx}/{len(targets_to_process)}] {sender} ({count} msgs)...", end=' ')
        unsub_ok = False
        method_used = 'none'

        parsed = _parse_list_unsubscribe(lu)
        if parsed:
            one_click = bool(lup and 'one-click' in lup.lower())
            unsub_ok, method_used = _execute_unsubscribe(gmail, parsed, one_click)
            if unsub_ok:
                results['unsubscribed'] += 1
                print(f"unsub ok ({method_used})", end='')
            else:
                results['failed'] += 1
                print("unsub failed", end='')
        else:
            results['archive_only'] += 1
            print("no List-Unsubscribe header", end='')

        # Clean up existing inbox messages from this sender.
        if not args.no_archive:
            if args.delete:
                gmail.batch_modify_messages(
                    sender_msgs[sender], add_labels=['TRASH'], remove_labels=['INBOX']
                )
                results['archived'] += len(sender_msgs[sender])
                print(f" → trashed {len(sender_msgs[sender])}")
            else:
                gmail.batch_modify_messages(sender_msgs[sender], remove_labels=['INBOX'])
                results['archived'] += len(sender_msgs[sender])
                print(f" → archived {len(sender_msgs[sender])}")
        else:
            print()

    print("\n" + "=" * 50)
    print("📊 Summary")
    print(f"   Unsubscribed:        {results['unsubscribed']}")
    print(f"   Failed unsubscribe:  {results['failed']}")
    print(f"   No unsub header:     {results['archive_only']}")
    cleanup_label = 'trashed' if args.delete else 'archived'
    print(f"   Inbox emails {cleanup_label}: {results['archived']:,}")
    print("=" * 50)


def _humans_exclusion() -> str:
    """Gmail search fragment that excludes the human whitelist."""
    return '-from:(' + ' OR '.join(HUMANS_WHITELIST) + ')'


def _find_label_id(gmail: 'GmailCLI', name: str) -> Optional[str]:
    """Find an existing label by exact name. Returns None if not found."""
    for L in gmail.get_labels():
        if L.get('name') == name:
            return L['id']
    return None


def _build_filter_preset(gmail: 'GmailCLI') -> List[Dict[str, Any]]:
    """Build the new filter set (in addition to upgrading existing filters).

    Uses the user's existing label taxonomy where possible. Returns Gmail API
    filter dicts: {name, criteria, action}.
    """
    label_newsletters = _find_label_id(gmail, '📧 Newsletters') or gmail.create_label('📧 Newsletters')
    label_notifications = _find_label_id(gmail, '💬 Notifications') or gmail.create_label('💬 Notifications')

    return [
        {
            'name': 'whitelist-humans (star + important + protect from spam)',
            'criteria': {'from': ' OR '.join(HUMANS_WHITELIST)},
            'action': {
                'addLabelIds': ['STARRED', 'IMPORTANT'],
                'removeLabelIds': ['SPAM'],
            },
        },
        {
            'name': 'has:list catch-all → 📧 Newsletters + archive + read',
            'criteria': {'query': 'has:list ' + _humans_exclusion()},
            'action': {
                'addLabelIds': [label_newsletters],
                'removeLabelIds': ['INBOX', 'UNREAD'],
            },
        },
        {
            'name': 'previously-unsubscribed (2026-05-14) → 💬 Notifications + archive',
            'criteria': {'from': ' OR '.join(UNSUBBED_SENDERS)},
            'action': {
                'addLabelIds': [label_notifications],
                'removeLabelIds': ['INBOX', 'UNREAD'],
            },
        },
        {
            'name': 'killlist (vetted noise senders) → 💬 Notifications + archive',
            'criteria': {'from': ' OR '.join(VETTED_KILL_LIST)},
            'action': {
                'addLabelIds': [label_notifications],
                'removeLabelIds': ['INBOX', 'UNREAD'],
            },
        },
    ]


# Filter actions that mean "this is a protect/route filter, leave alone"
_PROTECT_LABEL_IDS = {'STARRED', 'IMPORTANT'}
_TRASH_LABEL_IDS = {'TRASH', 'SPAM'}


def _upgrade_existing_filters(
    gmail: 'GmailCLI',
    dry_run: bool = False,
) -> Tuple[int, int]:
    """Add INBOX and UNREAD removal to label-and-archive filters.

    Skips:
    - protect filters (whitelist-humans pattern: adds STARRED/IMPORTANT)
    - trash/block filters (adds TRASH/SPAM — they're already handling their own routing)
    - filters with no label add (nothing to categorize as)
    - filters that already have both INBOX and UNREAD in remove (already optimal)

    Returns (upgraded_count, skipped_count).
    """
    existing = _list_filters(gmail)
    upgraded = 0
    skipped = 0
    for f in existing:
        action = f.get('action', {})
        add_labels = action.get('addLabelIds', [])
        remove_labels = set(action.get('removeLabelIds', []))
        add_set = set(add_labels)
        # Skip protect filters (whitelist-humans) — these should keep mail in inbox.
        if add_set & _PROTECT_LABEL_IDS:
            skipped += 1
            continue
        # Skip trash/block filters — they manage their own state.
        if add_set & _TRASH_LABEL_IDS:
            skipped += 1
            continue
        # Skip filters that don't apply a label.
        if not add_labels:
            skipped += 1
            continue
        # Already at target state.
        if {'INBOX', 'UNREAD'}.issubset(remove_labels):
            skipped += 1
            continue
        new_remove = sorted(remove_labels | {'INBOX', 'UNREAD'})
        new_action = {
            'addLabelIds': add_labels,
            'removeLabelIds': new_remove,
        }
        if action.get('forward'):
            new_action['forward'] = action['forward']
        label_preview = ','.join(add_labels)
        from_preview = (f.get('criteria', {}).get('from', '')
                        or f.get('criteria', {}).get('query', ''))[:60]
        if dry_run:
            print(f"  UPGRADE: +archive+read  labels={label_preview}  from={from_preview}...")
            upgraded += 1
            continue
        try:
            gmail.service.users().settings().filters().create(
                userId='me',
                body={'criteria': f['criteria'], 'action': new_action},
            ).execute()
            gmail.service.users().settings().filters().delete(
                userId='me', id=f['id']
            ).execute()
            print(f"  ✅ upgraded  labels={label_preview}  from={from_preview}...")
            upgraded += 1
        except HttpError as e:
            print(f"  ❌ failed upgrade  id={f['id']}: {e}")
    return upgraded, skipped


def _list_filters(gmail: 'GmailCLI') -> List[Dict[str, Any]]:
    """List all existing Gmail filters."""
    try:
        resp = gmail.service.users().settings().filters().list(userId='me').execute()
        return resp.get('filter', [])
    except HttpError as e:
        print(f"❌ Error listing filters: {e}")
        return []


def _create_block_filter(gmail: 'GmailCLI', sender: str) -> bool:
    """Create a Gmail filter that auto-trashes mail from `sender`.

    Used as escalation when an unsubscribe failed to stick. Returns True on
    success, False on failure. Skips creation if an equivalent filter already
    exists.
    """
    # Dedup against existing filters with the same from: criterion.
    for f in _list_filters(gmail):
        crit = f.get('criteria', {})
        if crit.get('from', '').strip().lower() == sender.strip().lower():
            return True  # already blocked
    try:
        gmail.service.users().settings().filters().create(
            userId='me',
            body={
                'criteria': {'from': sender},
                'action': {
                    'addLabelIds': ['TRASH'],
                    'removeLabelIds': ['INBOX', 'UNREAD'],
                },
            },
        ).execute()
        return True
    except HttpError as e:
        print(f"  ❌ failed to create block filter for {sender}: {e}")
        return False


def cmd_filters(args):
    """Create/list/delete Gmail filters."""
    gmail = GmailCLI(args.email)

    if args.subaction == 'list':
        filters = _list_filters(gmail)
        if not filters:
            print("No filters configured.")
            return
        print(f"📋 {len(filters)} existing filter(s):\n")
        for f in filters:
            crit = f.get('criteria', {})
            act = f.get('action', {})
            print(f"  id={f['id']}")
            if crit.get('from'): print(f"    from:  {crit['from'][:90]}")
            if crit.get('query'): print(f"    query: {crit['query'][:90]}")
            if act.get('addLabelIds'): print(f"    +labels: {act['addLabelIds']}")
            if act.get('removeLabelIds'): print(f"    -labels: {act['removeLabelIds']}")
            print()
        return

    if args.subaction == 'delete':
        if args.id == 'all':
            existing = _list_filters(gmail)
            print(f"⚠️  About to delete {len(existing)} filter(s).")
            if not args.yes:
                if input("Type 'DELETE' to confirm: ") != 'DELETE':
                    print("Cancelled.")
                    return
            for f in existing:
                gmail.service.users().settings().filters().delete(
                    userId='me', id=f['id']
                ).execute()
                print(f"  deleted {f['id']}")
            print("✅ All filters deleted.")
        else:
            gmail.service.users().settings().filters().delete(
                userId='me', id=args.id
            ).execute()
            print(f"✅ Deleted filter {args.id}")
        return

    # Default: upgrade existing filters + apply preset.
    print("🔧 Step 1: Upgrade existing label-only filters with archive action\n")
    upgraded, skipped_existing = _upgrade_existing_filters(gmail, dry_run=args.dry_run)
    print(f"  → {upgraded} upgraded, {skipped_existing} unchanged\n")

    print("🏗  Step 2: Build new filter preset (humans / has:list / unsubbed / killlist)\n")
    preset = _build_filter_preset(gmail)

    # Re-fetch existing filters after upgrade for dedup.
    existing = _list_filters(gmail)
    existing_keys = set()
    for f in existing:
        crit = f.get('criteria', {})
        key = (crit.get('from', ''), crit.get('query', ''))
        existing_keys.add(key)

    if args.dry_run:
        print("📋 Filters that would be created:\n")
        for i, f in enumerate(preset, 1):
            key = (f['criteria'].get('from', ''), f['criteria'].get('query', ''))
            status = '(SKIP — already exists)' if key in existing_keys else '(NEW)'
            print(f"{i}. {f['name']} {status}")
            if f['criteria'].get('from'):
                print(f"   from:    {f['criteria']['from'][:120]}")
            if f['criteria'].get('query'):
                print(f"   query:   {f['criteria']['query'][:120]}")
            print(f"   action:  add={f['action'].get('addLabelIds', [])} "
                  f"remove={f['action'].get('removeLabelIds', [])}")
            print()
        print("🔍 Dry run — no filters created. Remove --dry-run to apply.")
        return

    created = 0
    skipped_preset = 0
    failed = 0
    for i, f in enumerate(preset, 1):
        key = (f['criteria'].get('from', ''), f['criteria'].get('query', ''))
        if key in existing_keys:
            print(f"[{i}/{len(preset)}] {f['name']}: SKIP (already exists)")
            skipped_preset += 1
            continue
        try:
            gmail.service.users().settings().filters().create(
                userId='me',
                body={'criteria': f['criteria'], 'action': f['action']},
            ).execute()
            print(f"[{i}/{len(preset)}] {f['name']}: ✅ created")
            created += 1
        except HttpError as e:
            print(f"[{i}/{len(preset)}] {f['name']}: ❌ failed — {e}")
            failed += 1

    print(f"\n📊 Summary:")
    print(f"   Existing upgraded:  {upgraded}")
    print(f"   New created:        {created}")
    print(f"   Skipped (dup):      {skipped_preset}")
    print(f"   Failed:             {failed}")


def cmd_verify(args):
    """Verify previously-unsubscribed senders are silent. Optionally escalate."""
    gmail = GmailCLI(args.email)

    if not UNSUBBED_SENDERS:
        print("ℹ️  lists/unsubbed.yaml is empty — nothing to verify.")
        return

    # --since wins over --days for precision (counts only mail arrived after that date).
    if args.since:
        window = f'after:{args.since.replace("-", "/")}'
        window_desc = f"since {args.since}"
    else:
        window = f'newer_than:{args.days}d'
        window_desc = f"the last {args.days} days"

    print(f"🔍 Verifying {len(UNSUBBED_SENDERS)} previously-unsubscribed senders "
          f"against {window_desc}...\n")

    stuck = []  # (sender, count)
    silent = []
    for sender in UNSUBBED_SENDERS:
        query = f'from:{sender} {window}'
        messages = gmail.search_messages(query, max_results=args.limit)
        count = len(messages)
        if count > 0:
            stuck.append((sender, count))
        else:
            silent.append(sender)

    # Sort stuck by message count, descending.
    stuck.sort(key=lambda t: t[1], reverse=True)

    if stuck:
        print(f"❌ STUCK — {len(stuck)} senders still arriving:")
        for sender, count in stuck:
            print(f"   {count:>4}  {sender}")
        print()
    print(f"✅ SILENT — {len(silent)} unsubscribes appear to have stuck.")

    if not stuck:
        return

    if not args.escalate:
        print("\n💡 Re-run with --escalate to auto-create block filters "
              "(auto-trash) for stuck senders.")
        return

    print(f"\n⚠️  Escalating {len(stuck)} stuck senders → creating block filters...\n")
    blocked = 0
    failed = 0
    for sender, count in stuck:
        if _create_block_filter(gmail, sender):
            print(f"  ✅ blocked  {sender}  ({count} msgs in window)")
            blocked += 1
        else:
            failed += 1

    print(f"\n📊 Escalation summary:")
    print(f"   Block filters created: {blocked}")
    print(f"   Failed:                {failed}")


def cmd_autopilot(args):
    """Run the full safe-by-default cleanup workflow in one shot.

    Sequence:
      1. filters apply       → upgrade existing + create preset (idempotent)
      2. unsubscribe         → kill noise from the last 30 days, min-count 2
      3. mark-read           → clear the archived-but-unread backlog
      4. verify              → check stickiness; optionally escalate stuck senders

    Safe to run repeatedly. Use --dry-run to preview without taking action.
    """
    from argparse import Namespace

    print("🤖 gmail-cleanup autopilot — full inbox cleanup\n")
    print("=" * 72)

    print("\n━━━ Phase 1/4: Apply Gmail filters ━━━\n")
    cmd_filters(Namespace(
        email=args.email,
        subaction='apply',
        dry_run=args.dry_run,
    ))

    print("\n━━━ Phase 2/4: Unsubscribe noise senders (last 30d, min-count 2) ━━━\n")
    cmd_unsubscribe(Namespace(
        email=args.email,
        days=30,
        min_count=2,
        limit=2000,
        dry_run=args.dry_run,
        no_archive=False,
        delete=False,
    ))

    if args.dry_run:
        print("\n🔍 Dry run — skipping phases 3 and 4 (mark-read, verify).")
        print("\n" + "=" * 72)
        print("🤖 Autopilot dry-run complete. Remove --dry-run to execute.")
        return

    print("\n━━━ Phase 3/4: Mark archived-unread as read ━━━\n")
    cmd_mark_read(Namespace(
        email=args.email,
        query='is:unread -in:inbox',
        limit=10000,
        yes=True,
    ))

    print("\n━━━ Phase 4/4: Verify previously-unsubscribed senders ━━━\n")
    cmd_verify(Namespace(
        email=args.email,
        days=14,
        since=None,
        limit=100,
        escalate=args.escalate,
    ))

    print("\n" + "=" * 72)
    print("🎉 Autopilot complete. Inbox state:\n")
    cmd_stats(Namespace(email=args.email))


def cmd_mark_read(args):
    """Bulk-mark matching messages as read."""
    gmail = GmailCLI(args.email)

    query = args.query
    print(f"🔍 Searching for unread messages matching: {query}\n")
    messages = gmail.search_messages(query, max_results=args.limit)

    if not messages:
        print("✅ No unread messages match — nothing to do.")
        return

    print(f"Found {len(messages):,} unread messages.")

    if not args.yes:
        response = input(f"\n📖 Mark all {len(messages):,} as read? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cancelled")
            return

    print("\n📖 Marking as read...")
    batch_size = 1000
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        msg_ids = [msg['id'] for msg in batch]
        gmail.batch_modify_messages(msg_ids, remove_labels=['UNREAD'])
        print(f"   {min(i + batch_size, len(messages)):,}/{len(messages):,}", end='\r')

    print(f"\n✅ Marked {len(messages):,} messages as read.")


def cmd_archive(args):
    """Archive emails matching criteria"""
    gmail = GmailCLI(args.email)

    # Build query
    query_parts = []

    if args.older_than:
        date_ago = datetime.now() - timedelta(days=args.older_than)
        date_str = date_ago.strftime('%Y/%m/%d')
        query_parts.append(f'before:{date_str}')

    if args.sender:
        query_parts.append(f'from:{args.sender}')

    if args.category:
        query_parts.append(f'category:{args.category}')

    if args.label:
        query_parts.append(f'label:{args.label}')

    if args.query:
        query_parts.append(args.query)

    if not query_parts:
        print("❌ Error: Must specify at least one filter (--older-than, --sender, --category, --label, or --query)")
        return

    query = ' '.join(query_parts)
    print(f"🔍 Searching for emails matching: {query}\n")

    messages = gmail.search_messages(query, max_results=args.limit)

    if not messages:
        print("✅ No emails found matching criteria")
        return

    print(f"Found {len(messages):,} emails")

    if not args.yes:
        response = input(f"\n⚠️  Archive {len(messages)} emails? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cancelled")
            return

    print("\n📦 Archiving emails...")

    # Archive in batches of 1000
    batch_size = 1000
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        msg_ids = [msg['id'] for msg in batch]

        # Remove INBOX label to archive
        gmail.batch_modify_messages(msg_ids, remove_labels=['INBOX'])

        print(f"Archived {min(i + batch_size, len(messages)):,}/{len(messages):,}", end='\r')

    print(f"\n✅ Archived {len(messages):,} emails")


def cmd_delete(args):
    """Delete emails (move to trash)"""
    gmail = GmailCLI(args.email)

    # Build query (same as archive)
    query_parts = []

    if args.older_than:
        date_ago = datetime.now() - timedelta(days=args.older_than)
        date_str = date_ago.strftime('%Y/%m/%d')
        query_parts.append(f'before:{date_str}')

    if args.sender:
        query_parts.append(f'from:{args.sender}')

    if args.category:
        query_parts.append(f'category:{args.category}')

    if args.label:
        query_parts.append(f'label:{args.label}')

    if args.query:
        query_parts.append(args.query)

    if not query_parts:
        print("❌ Error: Must specify at least one filter")
        return

    query = ' '.join(query_parts)
    print(f"🔍 Searching for emails matching: {query}\n")

    messages = gmail.search_messages(query, max_results=args.limit)

    if not messages:
        print("✅ No emails found matching criteria")
        return

    print(f"Found {len(messages):,} emails")

    if not args.yes:
        print(f"\n⚠️  WARNING: This will move {len(messages)} emails to trash!")
        print("They will be permanently deleted after 30 days.")
        response = input("Type 'DELETE' to confirm: ")
        if response != 'DELETE':
            print("❌ Cancelled")
            return

    print("\n🗑️  Moving emails to trash...")

    # Add TRASH label in batches
    batch_size = 1000
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        msg_ids = [msg['id'] for msg in batch]

        gmail.batch_modify_messages(msg_ids, add_labels=['TRASH'], remove_labels=['INBOX'])

        print(f"Deleted {min(i + batch_size, len(messages)):,}/{len(messages):,}", end='\r')

    print(f"\n✅ Moved {len(messages):,} emails to trash")


def cmd_label(args):
    """Create label and apply to matching emails"""
    gmail = GmailCLI(args.email)

    # Create or get label
    print(f"📝 Creating/finding label: {args.name}")
    label_id = gmail.create_label(args.name)

    if not label_id:
        print("❌ Failed to create label")
        return

    print(f"✅ Label ID: {label_id}\n")

    if args.query:
        print(f"🔍 Searching for emails matching: {args.query}\n")
        messages = gmail.search_messages(args.query, max_results=args.limit)

        if not messages:
            print("✅ No emails found matching criteria")
            return

        print(f"Found {len(messages):,} emails")

        if not args.yes:
            response = input(f"\n⚠️  Apply label to {len(messages)} emails? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("❌ Cancelled")
                return

        print("\n🏷️  Applying label...")

        # Apply label in batches
        batch_size = 1000
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            msg_ids = [msg['id'] for msg in batch]

            gmail.batch_modify_messages(msg_ids, add_labels=[label_id])

            print(f"Labeled {min(i + batch_size, len(messages)):,}/{len(messages):,}", end='\r')

        print(f"\n✅ Applied label to {len(messages):,} emails")

        if args.archive:
            print("\n📦 Archiving labeled emails...")
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                msg_ids = [msg['id'] for msg in batch]
                gmail.batch_modify_messages(msg_ids, remove_labels=['INBOX'])
            print("✅ Archived")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Gmail Cleanup CLI - Powerful email management from the terminal',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show inbox stats
  gmail-cli stats

  # Find top senders
  gmail-cli top-senders --count 20 --days 365

  # Find subscriptions
  gmail-cli subscriptions --min-count 5

  # Archive old promotions
  gmail-cli archive --category promotions --older-than 90

  # Archive from specific sender
  gmail-cli archive --sender "newsletter@example.com" --yes

  # Create and apply label
  gmail-cli label --name "Receipts" --query "receipt OR invoice" --archive

  # Delete old social media notifications
  gmail-cli delete --older-than 60 --query "facebook OR twitter OR instagram"
"""
    )

    # Global options
    parser.add_argument('--email', default=os.getenv('USER_GOOGLE_EMAIL', ''),
                       help='Gmail address (default: from USER_GOOGLE_EMAIL env var)')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Autopilot command — the Swiss army knife "do everything" entry point
    parser_auto = subparsers.add_parser(
        'autopilot',
        help='One-command cleanup: apply filters → unsubscribe → mark-read → verify',
    )
    parser_auto.add_argument('--dry-run', action='store_true',
                             help='Preview without taking action (skips mark-read + verify)')
    parser_auto.add_argument('--escalate', action='store_true',
                             help='In phase 4, auto-create block filters for stuck senders')
    parser_auto.set_defaults(func=cmd_autopilot)

    # Stats command
    parser_stats = subparsers.add_parser('stats', help='Show inbox statistics')
    parser_stats.set_defaults(func=cmd_stats)

    # Top senders command
    parser_top = subparsers.add_parser('top-senders', help='Find top email senders')
    parser_top.add_argument('--count', type=int, default=20, help='Number of top senders to show')
    parser_top.add_argument('--days', type=int, default=365, help='Days to look back')
    parser_top.add_argument('--limit', type=int, default=5000, help='Max messages to analyze')
    parser_top.add_argument('--unread', action='store_true', help='Only count unread emails')
    parser_top.set_defaults(func=cmd_top_senders)

    # Subscriptions command
    parser_subs = subparsers.add_parser('subscriptions', help='Find email subscriptions')
    parser_subs.add_argument('--count', type=int, default=30, help='Number to show')
    parser_subs.add_argument('--days', type=int, default=180, help='Days to look back')
    parser_subs.add_argument('--limit', type=int, default=5000, help='Max messages to analyze')
    parser_subs.add_argument('--min-count', type=int, default=5, help='Min emails per sender to show')
    parser_subs.add_argument('--unread', action='store_true', help='Only count unread emails')
    parser_subs.set_defaults(func=cmd_find_subscriptions)

    # Unsubscribe command
    parser_unsub = subparsers.add_parser(
        'unsubscribe',
        help='Find subscription senders and execute their List-Unsubscribe links',
    )
    parser_unsub.add_argument('--days', type=int, default=60,
                              help='Inbox window to scan, in days (default: 60)')
    parser_unsub.add_argument('--min-count', type=int, default=5,
                              help='Minimum inbox messages from a sender to auto-target (default: 5)')
    parser_unsub.add_argument('--limit', type=int, default=2000,
                              help='Max messages to analyze (default: 2000)')
    parser_unsub.add_argument('--dry-run', action='store_true',
                              help='Preview the plan without firing any requests')
    parser_unsub.add_argument('--no-archive', action='store_true',
                              help="Don't archive existing inbox emails after unsubscribing")
    parser_unsub.add_argument('--delete', action='store_true',
                              help='Move existing emails to Trash instead of archiving '
                                   '(auto-purges after 30 days). Ignored if --no-archive.')
    parser_unsub.set_defaults(func=cmd_unsubscribe)

    # Filters command (apply preset / list / delete)
    parser_filters = subparsers.add_parser(
        'filters',
        help='Create, list, or delete Gmail filters (auto-archive rules)',
    )
    filter_subs = parser_filters.add_subparsers(dest='subaction')
    fs_apply = filter_subs.add_parser('apply', help='Apply the standard auto-archive preset')
    fs_apply.add_argument('--dry-run', action='store_true', help='Preview without creating')
    fs_list = filter_subs.add_parser('list', help='List existing filters')
    fs_del = filter_subs.add_parser('delete', help='Delete a filter')
    fs_del.add_argument('--id', required=True, help='Filter ID, or "all" to delete every filter')
    fs_del.add_argument('--yes', action='store_true', help='Skip confirmation when --id=all')
    parser_filters.set_defaults(func=cmd_filters, subaction='apply', dry_run=False)

    # Verify command (stickiness check for previously-unsubscribed senders)
    parser_verify = subparsers.add_parser(
        'verify',
        help='Check whether previously-unsubscribed senders are still arriving',
    )
    parser_verify.add_argument('--days', type=int, default=14,
                               help='Window to check, in days (default: 14)')
    parser_verify.add_argument('--since',
                               help='Only count mail arrived after this date (YYYY-MM-DD). '
                                    'More precise than --days for verifying a specific unsubscribe run.')
    parser_verify.add_argument('--limit', type=int, default=100,
                               help='Max messages to count per sender (default: 100)')
    parser_verify.add_argument('--escalate', action='store_true',
                               help='Auto-create a block filter (auto-trash) for each stuck sender')
    parser_verify.set_defaults(func=cmd_verify)

    # Mark-read command — clean up the archived-but-unread backlog
    parser_mark_read = subparsers.add_parser(
        'mark-read',
        help='Bulk-mark matching messages as read (e.g., archived-unread backlog)',
    )
    parser_mark_read.add_argument('--query', default='is:unread -in:inbox',
                                  help="Gmail search query (default: 'is:unread -in:inbox' — "
                                       "everything archived and unread)")
    parser_mark_read.add_argument('--limit', type=int, default=10000,
                                  help='Max messages to mark (default: 10000)')
    parser_mark_read.add_argument('--yes', action='store_true',
                                  help='Skip confirmation prompt')
    parser_mark_read.set_defaults(func=cmd_mark_read)

    # Archive command
    parser_archive = subparsers.add_parser('archive', help='Archive emails')
    parser_archive.add_argument('--older-than', type=int, help='Archive emails older than N days')
    parser_archive.add_argument('--sender', help='Archive emails from specific sender')
    parser_archive.add_argument('--category', choices=['promotions', 'social', 'updates', 'forums'],
                               help='Archive emails in category')
    parser_archive.add_argument('--label', help='Archive emails with label')
    parser_archive.add_argument('--query', help='Custom Gmail search query')
    parser_archive.add_argument('--limit', type=int, default=10000, help='Max emails to process')
    parser_archive.add_argument('--yes', action='store_true', help='Skip confirmation')
    parser_archive.set_defaults(func=cmd_archive)

    # Delete command
    parser_delete = subparsers.add_parser('delete', help='Delete emails (move to trash)')
    parser_delete.add_argument('--older-than', type=int, help='Delete emails older than N days')
    parser_delete.add_argument('--sender', help='Delete emails from specific sender')
    parser_delete.add_argument('--category', choices=['promotions', 'social', 'updates', 'forums'],
                              help='Delete emails in category')
    parser_delete.add_argument('--label', help='Delete emails with label')
    parser_delete.add_argument('--query', help='Custom Gmail search query')
    parser_delete.add_argument('--limit', type=int, default=10000, help='Max emails to process')
    parser_delete.add_argument('--yes', action='store_true', help='Skip confirmation')
    parser_delete.set_defaults(func=cmd_delete)

    # Label command
    parser_label = subparsers.add_parser('label', help='Create and apply labels')
    parser_label.add_argument('--name', required=True, help='Label name')
    parser_label.add_argument('--query', help='Gmail search query for emails to label')
    parser_label.add_argument('--archive', action='store_true', help='Archive after labeling')
    parser_label.add_argument('--limit', type=int, default=10000, help='Max emails to process')
    parser_label.add_argument('--yes', action='store_true', help='Skip confirmation')
    parser_label.set_defaults(func=cmd_label)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Load environment variables from .env before anything else
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key, value)

    # Re-check email after .env load
    if not args.email:
        args.email = os.getenv('USER_GOOGLE_EMAIL', '')

    if not args.email:
        print("Error: Email address required. Set USER_GOOGLE_EMAIL env var or use --email")
        sys.exit(1)

    # Run command
    args.func(args)


if __name__ == '__main__':
    main()
