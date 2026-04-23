from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AccountNumber(BaseModel):
    account_number: str = Field(alias="accountNumber")
    hash_value: str = Field(alias="hashValue")

    model_config = {"populate_by_name": True}


class Account(BaseModel):
    account_number: str
    account_hash: str
    cash_balance: float
    account_value: float
    account_type: str


class Position(BaseModel):
    ticker: str
    quantity: float
    average_price: float
    market_value: float
    unrealized_pnl: float


class Order(BaseModel):
    order_id: str
    ticker: str
    action: str
    quantity: float
    order_type: str
    limit_price: float | None
    status: str
    entered_time: datetime
