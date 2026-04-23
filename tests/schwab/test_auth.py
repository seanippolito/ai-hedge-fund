from src.schwab.exceptions import SchwabAuthError, SchwabAPIError


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
