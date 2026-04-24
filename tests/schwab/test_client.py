from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.schwab.client import SchwabClient
from src.schwab.exceptions import SchwabAPIError, SchwabAuthError
from src.schwab.models import Account, AccountNumber, Order, Position


MOCK_ACCOUNT_NUMBERS = [
    {"accountNumber": "12345678", "hashValue": "abc123hash"}
]

MOCK_ACCOUNT = [
    {
        "securitiesAccount": {
            "type": "MARGIN",
            "accountNumber": "12345678",
            "currentBalances": {
                "cashBalance": 25000.0,
                "liquidationValue": 100000.0,
            },
            "positions": [],
        }
    }
]

MOCK_POSITIONS_RESPONSE = {
    "securitiesAccount": {
        "type": "MARGIN",
        "accountNumber": "12345678",
        "currentBalances": {
            "cashBalance": 25000.0,
            "liquidationValue": 100000.0,
        },
        "positions": [
            {
                "instrument": {"symbol": "AAPL"},
                "longQuantity": 10.0,
                "shortQuantity": 0.0,
                "averagePrice": 150.0,
                "marketValue": 1700.0,
                "longOpenProfitLoss": 200.0,
            }
        ],
    }
}

MOCK_ORDERS = [
    {
        "orderId": "ORD001",
        "orderLegCollection": [
            {
                "instrument": {"symbol": "MSFT"},
                "instruction": "BUY",
                "quantity": 5.0,
            }
        ],
        "orderType": "LIMIT",
        "price": 380.0,
        "status": "WORKING",
        "enteredTime": "2026-04-18T09:30:00+00:00",
    }
]


def _mock_get(status: int, body) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    return r


@pytest.fixture
def client(valid_token_file, monkeypatch):
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "cid")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "csecret")
    return SchwabClient(token_path=str(valid_token_file))


def test_get_account_numbers(client):
    with patch("src.schwab.client.requests.get", return_value=_mock_get(200, MOCK_ACCOUNT_NUMBERS)):
        result = client.get_account_numbers()
    assert len(result) == 1
    assert isinstance(result[0], AccountNumber)
    assert result[0].account_number == "12345678"
    assert result[0].hash_value == "abc123hash"


def test_get_accounts(client):
    # get_accounts makes two sequential calls: /accountNumbers then /accounts
    with patch("src.schwab.client.requests.get", side_effect=[
        _mock_get(200, MOCK_ACCOUNT_NUMBERS),
        _mock_get(200, MOCK_ACCOUNT),
    ]):
        result = client.get_accounts()
    assert len(result) == 1
    assert isinstance(result[0], Account)
    assert result[0].account_number == "12345678"
    assert result[0].account_hash == "abc123hash"
    assert result[0].cash_balance == 25000.0
    assert result[0].account_value == 100000.0
    assert result[0].account_type == "MARGIN"


def test_get_positions(client):
    with patch("src.schwab.client.requests.get", return_value=_mock_get(200, MOCK_POSITIONS_RESPONSE)):
        result = client.get_positions("abc123hash")
    assert len(result) == 1
    assert isinstance(result[0], Position)
    assert result[0].ticker == "AAPL"
    assert result[0].quantity == 10.0
    assert result[0].average_price == 150.0
    assert result[0].market_value == 1700.0
    assert result[0].unrealized_pnl == 200.0


def test_get_orders(client):
    with patch("src.schwab.client.requests.get", return_value=_mock_get(200, MOCK_ORDERS)):
        result = client.get_orders("abc123hash")
    assert len(result) == 1
    assert isinstance(result[0], Order)
    assert result[0].ticker == "MSFT"
    assert result[0].action == "BUY"
    assert result[0].order_type == "LIMIT"
    assert result[0].limit_price == 380.0
    assert result[0].status == "WORKING"
    assert result[0].entered_time == datetime(2026, 4, 18, 9, 30, tzinfo=timezone.utc)


def test_client_raises_auth_error_on_401(client):
    with patch("src.schwab.client.requests.get", return_value=_mock_get(401, {})):
        with pytest.raises(SchwabAuthError):
            client.get_accounts()


def test_client_raises_api_error_on_500(client):
    with patch("src.schwab.client.requests.get", return_value=_mock_get(500, {})):
        with pytest.raises(SchwabAPIError) as exc_info:
            client.get_accounts()
    assert exc_info.value.status_code == 500


def test_get_accounts_raises_auth_error_on_second_call_401(client):
    with patch("src.schwab.client.requests.get", side_effect=[
        _mock_get(200, MOCK_ACCOUNT_NUMBERS),
        _mock_get(401, {}),
    ]):
        with pytest.raises(SchwabAuthError):
            client.get_accounts()


def test_get_accounts_raises_api_error_on_second_call_500(client):
    with patch("src.schwab.client.requests.get", side_effect=[
        _mock_get(200, MOCK_ACCOUNT_NUMBERS),
        _mock_get(500, {}),
    ]):
        with pytest.raises(SchwabAPIError) as exc_info:
            client.get_accounts()
    assert exc_info.value.status_code == 500
