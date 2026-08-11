"""Custom Yahoo OAuth 2.0 flow with explicit fspt-w (Fantasy Sports write) scope.
Bypasses library defaults that omit the scope param.
Saves tokens to auth/oauth2.json (yahoo_oauth-compatible) AND .env.
"""
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

CK = os.environ["YAHOO_CONSUMER_KEY"]
CS = os.environ["YAHOO_CONSUMER_SECRET"]

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
REDIRECT = "oob"

# Try each of these scope values; Yahoo Fantasy docs are inconsistent
SCOPES_TO_TRY = ["fspt-w", "fspt-r", "openid fspt-w", "openid profile fspt-w"]


def build_auth_url(scope: str) -> str:
    params = {
        "client_id": CK,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": scope,
        "language": "en-us",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    r = requests.post(
        TOKEN_URL,
        data={
            "client_id": CK,
            "client_secret": CS,
            "redirect_uri": REDIRECT,
            "code": code,
            "grant_type": "authorization_code",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    return r.json()


def probe(access_token: str) -> tuple[int, str]:
    r = requests.get(
        "https://fantasysports.yahooapis.com/fantasy/v2/game/nfl?format=json",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return r.status_code, r.text[:500]


def save_tokens(tok: dict) -> None:
    out = {
        "consumer_key": CK,
        "consumer_secret": CS,
        "access_token": tok["access_token"],
        "refresh_token": tok["refresh_token"],
        "token_time": time.time(),
        "token_type": tok.get("token_type", "bearer"),
    }
    (ROOT / "auth" / "oauth2.json").write_text(json.dumps(out, indent=2))
    print(f"\nTokens saved to auth/oauth2.json")


def main() -> None:
    print("Trying scopes in order:", SCOPES_TO_TRY)
    print("For each, browser URL will be printed. Open it, approve, paste verifier.\n")

    for scope in SCOPES_TO_TRY:
        print(f"\n=== Scope: {scope} ===")
        url = build_auth_url(scope)
        print(f"OPEN THIS URL:\n{url}\n")
        code = input("Paste verifier code (or 'skip' to try next scope): ").strip()
        if code.lower() == "skip":
            continue
        try:
            tok = exchange_code(code)
        except requests.HTTPError as e:
            print(f"Token exchange failed: {e.response.text}")
            continue
        print(f"Token minted. Testing fantasy endpoint...")
        status, body = probe(tok["access_token"])
        print(f"HTTP {status}: {body}")
        if status == 200:
            print(f"\n*** SUCCESS with scope='{scope}' ***")
            save_tokens(tok)
            return
        print(f"Still failing with scope='{scope}'. Trying next.")

    print("\nAll scopes exhausted. App likely needs to be recreated OR Yahoo TOS not accepted.")


if __name__ == "__main__":
    main()
