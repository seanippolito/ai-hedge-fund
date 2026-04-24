from __future__ import annotations

import json
import time

import pytest


@pytest.fixture
def valid_token_file(tmp_path):
    token_data = {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "expires_at": time.time() + 3600,
    }
    token_file = tmp_path / "schwab_tokens.json"
    token_file.write_text(json.dumps(token_data))
    return token_file


@pytest.fixture
def expired_token_file(tmp_path):
    token_data = {
        "access_token": "old-access-token",
        "refresh_token": "old-refresh-token",
        "expires_at": time.time() - 60,
    }
    token_file = tmp_path / "schwab_tokens.json"
    token_file.write_text(json.dumps(token_data))
    return token_file
