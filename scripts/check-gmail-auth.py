#!/usr/bin/env python3
"""Credential and scope smoke test for Gmail API access."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

REQUIRED_ENV_VARS = (
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GMAIL_REFRESH_TOKEN",
    "GMAIL_USER_EMAIL",
)
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"


def _require_env_var(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise ValueError(f"Missing required environment variable: {name}")


def _build_credentials() -> Credentials:
    client_id = _require_env_var("GMAIL_CLIENT_ID")
    client_secret = _require_env_var("GMAIL_CLIENT_SECRET")
    refresh_token = _require_env_var("GMAIL_REFRESH_TOKEN")
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[GMAIL_SCOPE],
    )


def _list_messages(max_results: int = 5) -> dict[str, Any]:
    credentials = _build_credentials()
    credentials.refresh(Request())

    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    return (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, includeSpamTrash=False)
        .execute()
    )


def main() -> int:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        print(
            json.dumps({"ok": False, "error": "missing_env", "missing": missing}),
            file=sys.stderr,
        )
        return 2

    expected_email = os.getenv("GMAIL_USER_EMAIL", "")
    try:
        payload = _list_messages()
    except ValueError as exc:
        print(
            json.dumps({"ok": False, "error": "missing_env", "message": str(exc)}),
            file=sys.stderr,
        )
        return 2
    except HttpError as exc:
        body = ""
        try:
            body = exc.content.decode("utf-8")
        except Exception:
            body = str(exc)
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "gmail_http_error",
                    "status": exc.status_code,
                    "details": body,
                }
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            json.dumps({"ok": False, "error": "unexpected_error", "details": str(exc)}),
            file=sys.stderr,
        )
        return 1

    messages = payload.get("messages", [])
    print(
        json.dumps(
            {
                "ok": True,
                "scope": GMAIL_SCOPE,
                "gmail_user_email": expected_email,
                "message_count_returned": len(messages),
                "sample_message_ids": [m.get("id") for m in messages[:3]],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
