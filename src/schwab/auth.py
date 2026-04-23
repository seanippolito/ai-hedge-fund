from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import requests

from src.schwab.exceptions import SchwabAuthError


_REQUIRED_TOKEN_KEYS = {"access_token", "refresh_token", "expires_at"}


def save_tokens(path: Path, *, access_token: str, refresh_token: str, expires_at: float) -> None:
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }
    payload = json.dumps(data, indent=2)
    if sys.platform != "win32":
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            os.chmod(tmp, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(payload)
            os.replace(tmp, path)
        except Exception:
            os.unlink(tmp)
            raise
    else:
        path.write_text(payload)


def load_tokens(path: Path) -> dict:
    if not path.exists():
        raise SchwabAuthError(
            f"Token file not found at {path}. Run: poetry run python src/schwab/auth_setup.py"
        )
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SchwabAuthError(
            f"Token file at {path} is not valid JSON. Re-run auth setup."
        ) from exc
    missing = _REQUIRED_TOKEN_KEYS - data.keys()
    if missing:
        raise SchwabAuthError(
            f"Token file at {path} is missing keys: {sorted(missing)}. Re-run auth setup."
        )
    return data


_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"


def _refresh_tokens(path: Path, refresh_token: str) -> dict:
    client_id = os.environ.get("SCHWAB_CLIENT_ID")
    client_secret = os.environ.get("SCHWAB_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SchwabAuthError(
            "SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET must be set to refresh tokens."
        )

    try:
        response = requests.post(
            _TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(client_id, client_secret),
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        raise SchwabAuthError(f"Token refresh request failed: {exc}") from exc

    if response.status_code != 200:
        raise SchwabAuthError(f"Token refresh failed with status {response.status_code}")

    data = response.json()
    missing = {"access_token", "refresh_token", "expires_in"} - data.keys()
    if missing:
        raise SchwabAuthError(
            f"Token refresh response missing fields: {sorted(missing)}"
        )
    save_tokens(
        path,
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=time.time() + data["expires_in"],
    )
    return load_tokens(path)


def get_valid_token(token_path: Path | None = None) -> str:
    path = token_path or Path(os.environ["SCHWAB_TOKEN_PATH"])
    tokens = load_tokens(path)

    if time.time() >= tokens["expires_at"] - 60:
        tokens = _refresh_tokens(path, tokens["refresh_token"])

    return tokens["access_token"]
