#!/usr/bin/env python3
"""OAuth flow to obtain a Google Calendar + Gmail refresh_token.

Usage:
    uv run scripts/get_calendar_credentials.py

Requires a Google Cloud project with Calendar API enabled and an
OAuth 2.0 "Desktop app" client ID. Set these env vars or enter them
when prompted:

    CALENDAR_CLIENT_ID=<your-client-id>
    CALENDAR_CLIENT_SECRET=<your-client-secret>

The script opens a browser for consent. Google shows an auth code on
screen — paste it back here. The script exchanges it for a refresh_token
that covers both Gmail and Calendar scopes.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import webbrowser
from urllib.parse import urlencode

SCOPES = " ".join([
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
])
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def main() -> None:
    client_id = os.getenv("CALENDAR_CLIENT_ID", "").strip()
    client_secret = os.getenv("CALENDAR_CLIENT_SECRET", "").strip()

    if not client_id:
        client_id = input("CALENDAR_CLIENT_ID: ").strip()
    if not client_secret:
        client_secret = input("CALENDAR_CLIENT_SECRET: ").strip()

    if not client_id or not client_secret:
        print("ERROR: client_id and client_secret are required.", file=sys.stderr)
        sys.exit(1)

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",  # force refresh_token issuance
    }
    consent_url = f"{AUTH_URL}?{urlencode(params)}"

    print(f"\nOpening browser for consent...\n")
    webbrowser.open(consent_url)
    print(f"If the browser didn't open, visit:\n  {consent_url}\n")

    auth_code = input("Paste the auth code shown by Google: ").strip()
    if not auth_code:
        print("ERROR: No auth code provided.", file=sys.stderr)
        sys.exit(1)

    # Exchange code for tokens
    data = urlencode({
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read())

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print(
            "ERROR: No refresh_token returned. Make sure prompt=consent and "
            "access_type=offline are set (they are — this is unexpected).",
            file=sys.stderr,
        )
        print(f"Full response: {json.dumps(tokens, indent=2)}", file=sys.stderr)
        sys.exit(1)

    print("\n✓ Success. Update your .env with:\n")
    print(f"CALENDAR_CLIENT_ID={client_id}")
    print(f"CALENDAR_CLIENT_SECRET={client_secret}")
    print(f"CALENDAR_REFRESH_TOKEN={refresh_token}")
    print(f"GMAIL_REFRESH_TOKEN={refresh_token}  # same token, covers both scopes")
    print()


if __name__ == "__main__":
    main()
