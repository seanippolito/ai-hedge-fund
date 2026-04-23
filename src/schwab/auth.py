from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

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
