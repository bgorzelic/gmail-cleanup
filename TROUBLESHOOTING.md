# Troubleshooting

The 5 issues new users hit most often, and how to fix them. If something here doesn't match what you're seeing, open an [Issue](https://github.com/bgorzelic/gmail-cleanup/issues/new/choose).

---

## 1. "Access blocked: This app's request is invalid"

**Symptom:** During the OAuth flow (browser opens after `gmail-cleanup setup` or first `gmail-cleanup stats`), Google shows a red error page instead of the consent prompt.

**Cause:** You haven't configured the **OAuth consent screen** for your GCP project, OR you haven't added yourself as a **Test User** for an unverified app.

**Fix:**

1. Open [console.cloud.google.com/apis/credentials/consent](https://console.cloud.google.com/apis/credentials/consent) for your project.
2. If the screen is unconfigured: configure it. **User Type: External**, give it any name, supply your email for the support/dev contact fields, skip optional sections.
3. Scroll to **Test users** and add your Gmail address. Save.
4. Re-run `gmail-cleanup setup` or whatever you were running.

The wizard in v0.5.1+ walks you through this step (Step 3/7). If you're on an older version, this is the manual step.

---

## 2. "Could not find OAuth credentials"

**Symptom:**

```
❌ Could not find OAuth credentials.

Checked these locations for credentials.json:
  • /Users/you/.gmail_cli/credentials.json
  • /Users/you/cwd/credentials.json
  • ...
```

**Cause:** The `credentials.json` you downloaded from GCP Console isn't in any of the lookup paths.

**Fix (recommended):** Put it at `~/.gmail_cli/credentials.json`:

```bash
mkdir -p ~/.gmail_cli
mv ~/Downloads/client_secret_*.json ~/.gmail_cli/credentials.json
```

**Alternative:** Set `$GMAIL_CLEANUP_CREDENTIALS` to the path explicitly:

```bash
export GMAIL_CLEANUP_CREDENTIALS=/path/to/your/credentials.json
```

---

## 3. "Scope limit exceeded" / OAuth refuses 5+ scopes

**Symptom:** Consent prompt errors out, or only a subset of scopes is granted. Happens with `@gmail.com` accounts on unverified apps.

**Cause:** Google limits unverified OAuth apps in testing mode to ~25 scopes total, and stricter limits on what counts as "sensitive" scopes. gmail-cleanup requests 5 scopes — well under that — but if you have multiple unverified apps on the same project, you may hit aggregate limits.

**Fix:**
- For personal use, gmail-cleanup's 5 scopes work fine on a fresh test project.
- For workspace accounts (`@yourcompany.com`), ask your Workspace admin to allowlist the app, or verify the OAuth app in GCP (production-ish flow).

---

## 4. `gmail-cleanup schedule install` fails on Linux/Windows

**Symptom:**

```
❌ Scheduler is Mac-only in v0.5. Linux/Windows planned for v0.6.
```

**Cause:** v0.5 only ships launchd (macOS) support. Linux (systemd) and Windows (Task Scheduler) integrations are post-v0.5 ROADMAP items.

**Workaround until v0.6:** Set up a cron job manually:

```bash
# crontab -e — runs daily at 08:00 local time
0 8 * * * /path/to/.venv/bin/gmail-cleanup --email you@gmail.com autopilot --quiet >> ~/.gmail_cli/logs/autopilot.log 2>&1
```

---

## 5. Token expired / "invalid_grant" error

**Symptom:** After running fine for weeks, suddenly every command errors with `invalid_grant` or `Token has been expired or revoked`.

**Cause:** OAuth refresh tokens for unverified apps expire after **7 days** (Google policy). Once your app is verified or in production status, this becomes ~indefinite.

**Fix:**

```bash
# Delete the expired token cache for that account
rm ~/.gmail_cli/token_*your-email*.pkl 2>/dev/null
# Or, more carefully:
ls ~/.gmail_cli/ | grep token

# Re-run any command — it'll trigger a fresh OAuth flow
gmail-cleanup stats
```

If this happens weekly, look into the OAuth app verification process: [support.google.com/cloud/answer/9110914](https://support.google.com/cloud/answer/9110914).

---

## 6. `pytest` not found / `gmail-cleanup` not found after install

**Symptom:** Commands aren't recognized after `pip install`.

**Cause:** The virtual environment isn't activated, or you installed globally instead of in the venv.

**Fix:**

```bash
cd /path/to/gmail-cleanup
source .venv/bin/activate     # macOS / Linux
# or
.venv\Scripts\activate         # Windows
gmail-cleanup --help            # should now resolve
```

If you're using **`pipx`** (recommended for end-users), the binary is installed to `~/.local/bin/gmail-cleanup` — make sure `~/.local/bin` is in your `$PATH`.

---

## Still stuck?

Open a [bug report](https://github.com/bgorzelic/gmail-cleanup/issues/new?template=bug_report.md) with:

- Full command line you ran
- Full output / error message
- OS + Python version (`python3 --version`)
- gmail-cleanup version (`pip show gmail-cleanup | grep Version`)

For anything involving accidental loss of mail or KEEP-list bypass, mark the issue as safety-critical.
