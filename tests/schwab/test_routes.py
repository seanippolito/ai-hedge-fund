from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.backend.main import app
from src.schwab.exceptions import SchwabAPIError, SchwabAuthError
from src.schwab.models import Account, Order, Position


@pytest.fixture
def test_client():
    return TestClient(app)


MOCK_ACCOUNTS = [
    Account(
        account_number="12345678",
        account_hash="abc123hash",
        cash_balance=25000.0,
        account_value=100000.0,
        account_type="MARGIN",
    )
]

MOCK_POSITIONS = [
    Position(ticker="AAPL", quantity=10.0, average_price=150.0, market_value=1700.0, unrealized_pnl=200.0)
]

MOCK_ORDERS: list[Order] = []


def _patch_client(accounts=MOCK_ACCOUNTS, positions=MOCK_POSITIONS, orders=MOCK_ORDERS):
    mock = MagicMock()
    mock.get_accounts.return_value = accounts
    mock.get_positions.return_value = positions
    mock.get_orders.return_value = orders
    return mock


def test_account_endpoint_returns_200(test_client):
    with patch("app.backend.routes.schwab.SchwabClient", return_value=_patch_client()):
        response = test_client.get("/api/schwab/account")
    assert response.status_code == 200
    body = response.json()
    assert "accounts" in body
    assert "positions" in body
    assert "orders" in body
    assert body["accounts"][0]["account_number"] == "12345678"
    assert body["positions"][0]["ticker"] == "AAPL"


def test_account_endpoint_returns_502_on_api_error(test_client):
    mock_client = MagicMock()
    mock_client.get_accounts.side_effect = SchwabAPIError("upstream error", status_code=503)
    with patch("app.backend.routes.schwab.SchwabClient", return_value=mock_client):
        response = test_client.get("/api/schwab/account")
    assert response.status_code == 502


def test_account_endpoint_returns_401_on_auth_error(test_client):
    mock_client = MagicMock()
    mock_client.get_accounts.side_effect = SchwabAuthError("token rejected")
    with patch("app.backend.routes.schwab.SchwabClient", return_value=mock_client):
        response = test_client.get("/api/schwab/account")
    assert response.status_code == 401
