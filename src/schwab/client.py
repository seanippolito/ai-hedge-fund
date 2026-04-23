from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from src.schwab.auth import get_valid_token
from src.schwab.exceptions import SchwabAPIError, SchwabAuthError
from src.schwab.models import Account, AccountNumber, Order, Position

_BASE_URL = "https://api.schwabapi.com/trader/v1"


class SchwabClient:
    def __init__(self, token_path: str | None = None) -> None:
        raw = token_path or os.environ.get("SCHWAB_TOKEN_PATH")
        if not raw:
            raise SchwabAuthError(
                "SCHWAB_TOKEN_PATH env var is not set and no token_path was provided."
            )
        self._token_path = Path(raw)

    def _headers(self) -> dict[str, str]:
        token = get_valid_token(self._token_path)
        return {"Authorization": f"Bearer {token}"}

    def _get(self, path: str) -> dict | list:
        url = f"{_BASE_URL}{path}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=30)
        except requests.exceptions.RequestException as exc:
            raise SchwabAPIError(f"Request to {path} failed: {exc}") from exc
        if response.status_code == 401:
            raise SchwabAuthError("Access token rejected. Re-run auth setup.")
        if response.status_code != 200:
            raise SchwabAPIError(
                f"Schwab API returned {response.status_code} for {path}",
                status_code=response.status_code,
            )
        return response.json()

    def get_account_numbers(self) -> list[AccountNumber]:
        data = self._get("/accounts/accountNumbers")
        return [AccountNumber.model_validate(item) for item in data]

    def get_accounts(self) -> list[Account]:
        account_numbers_data = self._get("/accounts/accountNumbers")
        hash_map: dict[str, str] = {
            item["accountNumber"]: item["hashValue"] for item in account_numbers_data
        }
        data = self._get("/accounts")
        # Account, Position, Order models use snake_case; manual mapping from Schwab's camelCase
        accounts = []
        for item in data:
            sa = item["securitiesAccount"]
            balances = sa.get("currentBalances", {})
            acct_num = sa["accountNumber"]
            accounts.append(
                Account(
                    account_number=acct_num,
                    account_hash=hash_map.get(acct_num, ""),
                    cash_balance=balances.get("cashBalance", 0.0),
                    account_value=balances.get("liquidationValue", 0.0),
                    account_type=sa.get("type", "UNKNOWN"),
                )
            )
        return accounts

    def get_positions(self, account_hash: str) -> list[Position]:
        data = self._get(f"/accounts/{account_hash}?fields=positions")
        raw_positions = data.get("securitiesAccount", {}).get("positions", [])
        positions = []
        for p in raw_positions:
            quantity = p.get("longQuantity", 0.0) - p.get("shortQuantity", 0.0)
            positions.append(
                Position(
                    ticker=p["instrument"]["symbol"],
                    quantity=quantity,
                    average_price=p.get("averagePrice", 0.0),
                    market_value=p.get("marketValue", 0.0),
                    unrealized_pnl=p.get("longOpenProfitLoss", 0.0) + p.get("shortOpenProfitLoss", 0.0),
                )
            )
        return positions

    def get_orders(
        self,
        account_hash: str,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[Order]:
        now = datetime.now(tz=timezone.utc)
        from_dt = from_time or (now - timedelta(days=60))
        to_dt = to_time or now
        from_str = from_dt.strftime("%Y-%m-%dT%H:%M:%S")
        to_str = to_dt.strftime("%Y-%m-%dT%H:%M:%S")
        data = self._get(
            f"/accounts/{account_hash}/orders"
            f"?fromEnteredTime={from_str}&toEnteredTime={to_str}"
        )
        orders = []
        for o in data:
            leg = o.get("orderLegCollection", [{}])[0]
            entered_time_str = o.get("enteredTime")
            if not entered_time_str:
                raise SchwabAPIError(f"Order {o.get('orderId', '?')} missing enteredTime field")
            orders.append(
                Order(
                    order_id=str(o["orderId"]),
                    ticker=leg.get("instrument", {}).get("symbol", ""),
                    action=leg.get("instruction", ""),
                    quantity=leg.get("quantity", 0.0),
                    order_type=o.get("orderType", ""),
                    limit_price=o.get("price"),
                    status=o.get("status", ""),
                    entered_time=datetime.fromisoformat(entered_time_str),
                )
            )
        return orders
