"""
Run once to authenticate with Schwab and save OAuth tokens.

Usage:
    poetry run python src/schwab/auth_setup.py
"""
from __future__ import annotations

import os
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.schwab.auth import save_tokens
from src.schwab.exceptions import SchwabAuthError

_AUTH_URL = "https://api.schwabapis.com/v1/oauth/authorize"
_TOKEN_URL = "https://api.schwabapis.com/v1/oauth/token"


def run_auth_flow() -> None:
    load_dotenv()

    client_id = os.environ.get("SCHWAB_CLIENT_ID")
    client_secret = os.environ.get("SCHWAB_CLIENT_SECRET")
    redirect_uri = os.environ.get("SCHWAB_REDIRECT_URI")
    token_path_str = os.environ.get("SCHWAB_TOKEN_PATH")

    missing = [k for k, v in {
        "SCHWAB_CLIENT_ID": client_id,
        "SCHWAB_CLIENT_SECRET": client_secret,
        "SCHWAB_REDIRECT_URI": redirect_uri,
        "SCHWAB_TOKEN_PATH": token_path_str,
    }.items() if not v]
    if missing:
        raise SchwabAuthError(f"Missing required env vars: {missing}. Check your .env file.")

    token_path = Path(token_path_str)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "readonly",
    }
    auth_url = f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n=== Schwab OAuth2 Setup ===")
    print("Opening Schwab login in your browser...")
    print(f"\nIf the browser does not open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    print("After logging in, Schwab will redirect you to a URL that starts with:")
    print(f"  {redirect_uri}?code=...\n")
    redirect_response = input("Paste the full redirect URL here: ").strip()

    parsed = urllib.parse.urlparse(redirect_response)
    query = urllib.parse.parse_qs(parsed.query)
    if "code" not in query:
        raise SchwabAuthError("No authorization code found in the redirect URL.")
    code = query["code"][0]

    try:
        response = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            auth=(client_id, client_secret),
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        raise SchwabAuthError(f"Token exchange request failed: {exc}") from exc

    if response.status_code != 200:
        raise SchwabAuthError(
            f"Token exchange failed with status {response.status_code}: {response.text}"
        )

    data = response.json()
    missing_fields = {"access_token", "refresh_token", "expires_in"} - data.keys()
    if missing_fields:
        raise SchwabAuthError(f"Token response missing fields: {sorted(missing_fields)}")

    token_path.parent.mkdir(parents=True, exist_ok=True)
    save_tokens(
        token_path,
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=time.time() + data["expires_in"],
    )

    print(f"\n✓ Tokens saved to {token_path}")
    print("You can now run the application.")


if __name__ == "__main__":
    run_auth_flow()
