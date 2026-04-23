from __future__ import annotations

import json
import sys
from pathlib import Path

from src.schwab.exceptions import SchwabAuthError


def save_tokens(path: Path, *, access_token: str, refresh_token: str, expires_at: float) -> None:
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }
    path.write_text(json.dumps(data, indent=2))
    if sys.platform != "win32":
        path.chmod(0o600)


def load_tokens(path: Path) -> dict:
    if not path.exists():
        raise SchwabAuthError(f"Token file not found at {path}. Run: poetry run python src/schwab/auth_setup.py")
    return json.loads(path.read_text())
