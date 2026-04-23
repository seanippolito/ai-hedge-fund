from src.schwab.exceptions import SchwabAuthError, SchwabAPIError, SchwabError
from src.schwab.models import Account, AccountNumber, Order, Position
from datetime import datetime, timezone


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
