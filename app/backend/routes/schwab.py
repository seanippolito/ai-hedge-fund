from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.schwab.client import SchwabClient
from src.schwab.exceptions import SchwabAPIError, SchwabAuthError
from src.schwab.models import Account, Order, Position

router = APIRouter(prefix="/api/schwab", tags=["schwab"])


class AccountStateResponse(BaseModel):
    accounts: list[Account]
    positions: list[Position]
    orders: list[Order]


@router.get("/account", response_model=AccountStateResponse)
def get_account() -> AccountStateResponse:
    try:
        client = SchwabClient()
        accounts = client.get_accounts()

        all_positions: list[Position] = []
        all_orders: list[Order] = []
        for acct in accounts:
            all_positions.extend(client.get_positions(acct.account_hash))
            all_orders.extend(client.get_orders(acct.account_hash))

        return AccountStateResponse(
            accounts=accounts,
            positions=all_positions,
            orders=all_orders,
        )
    except SchwabAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except SchwabAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
