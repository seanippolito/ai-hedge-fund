import json
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.schwab.auth import load_tokens, save_tokens, get_valid_token
from src.schwab.exceptions import SchwabAuthError, SchwabAPIError, SchwabError
from src.schwab.models import Account, AccountNumber, Order, Position



def test_schwab_auth_error_is_exception():
    err = SchwabAuthError("token expired")
    assert isinstance(err, Exception)
    assert str(err) == "token expired"


def test_schwab_api_error_stores_status_code():
    err = SchwabAPIError("bad gateway", status_code=502)
    assert err.status_code == 502
    assert "bad gateway" in str(err)


def test_schwab_api_error_without_status_code():
    err = SchwabAPIError("unknown error")
    assert err.status_code is None


def test_schwab_auth_error_is_schwab_error():
    err = SchwabAuthError("token expired")
    assert isinstance(err, SchwabError)


def test_schwab_api_error_is_schwab_error():
    err = SchwabAPIError("bad gateway", status_code=502)
    assert isinstance(err, SchwabError)


def test_account_number_model():
    data = {"accountNumber": "12345678", "hashValue": "abc123hash"}
    an = AccountNumber.model_validate(data)
    assert an.account_number == "12345678"
    assert an.hash_value == "abc123hash"


def test_account_model():
    acct = Account(
        account_number="12345678",
        account_hash="abc123hash",
        cash_balance=25000.0,
        account_value=100000.0,
        account_type="MARGIN",
    )
    assert acct.cash_balance == 25000.0


def test_position_model():
    pos = Position(
        ticker="AAPL",
        quantity=10.0,
        average_price=150.0,
        market_value=1650.0,
        unrealized_pnl=150.0,
    )
    assert pos.ticker == "AAPL"


def test_order_model_optional_limit_price():
    order = Order(
        order_id="ORD001",
        ticker="MSFT",
        action="BUY",
        quantity=5.0,
        order_type="MARKET",
        limit_price=None,
        status="WORKING",
        entered_time=datetime(2026, 4, 18, 9, 30, tzinfo=timezone.utc),
    )
    assert order.limit_price is None
    assert order.order_type == "MARKET"


def test_save_tokens_writes_json(tmp_path):
    token_file = tmp_path / "tokens.json"
    save_tokens(token_file, access_token="acc", refresh_token="ref", expires_at=9999.0)
    data = json.loads(token_file.read_text())
    assert data["access_token"] == "acc"
    assert data["refresh_token"] == "ref"
    assert data["expires_at"] == 9999.0


@pytest.mark.skipif(sys.platform == "win32", reason="chmod not supported on Windows")
def test_save_tokens_sets_restricted_permissions(tmp_path):
    token_file = tmp_path / "tokens.json"
    save_tokens(token_file, access_token="acc", refresh_token="ref", expires_at=9999.0)
    mode = stat.S_IMODE(token_file.stat().st_mode)
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


def test_load_tokens_reads_correctly(valid_token_file):
    tokens = load_tokens(valid_token_file)
    assert tokens["access_token"] == "test-access-token"
    assert tokens["refresh_token"] == "test-refresh-token"
    assert tokens["expires_at"] > time.time()


def test_load_tokens_raises_when_file_missing(tmp_path):
    missing = tmp_path / "no_such_file.json"
    with pytest.raises(SchwabAuthError, match="Token file not found"):
        load_tokens(missing)


def test_get_valid_token_returns_token_when_not_expired(valid_token_file, monkeypatch):
    monkeypatch.setenv("SCHWAB_TOKEN_PATH", str(valid_token_file))
    token = get_valid_token()
    assert token == "test-access-token"


def test_get_valid_token_refreshes_when_expired(expired_token_file, monkeypatch):
    monkeypatch.setenv("SCHWAB_TOKEN_PATH", str(expired_token_file))
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test-secret")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new-access-token",
        "refresh_token": "new-refresh-token",
        "expires_in": 1800,
    }

    with patch("src.schwab.auth.requests.post", return_value=mock_response):
        token = get_valid_token()

    assert token == "new-access-token"
    saved = load_tokens(expired_token_file)
    assert saved["access_token"] == "new-access-token"


def test_get_valid_token_raises_on_failed_refresh(expired_token_file, monkeypatch):
    monkeypatch.setenv("SCHWAB_TOKEN_PATH", str(expired_token_file))
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "test-secret")

    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("src.schwab.auth.requests.post", return_value=mock_response):
        with pytest.raises(SchwabAuthError, match="Token refresh failed"):
            get_valid_token()
