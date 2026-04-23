"""
Verify Schwab connectivity by fetching and printing live account state.

Prerequisites:
    1. Add Schwab vars to your .env file
    2. Run: poetry run python src/schwab/auth_setup.py

Usage:
    poetry run python scripts/check_schwab.py
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from src.schwab.client import SchwabClient
from src.schwab.exceptions import SchwabAPIError, SchwabAuthError


def main() -> None:
    print("Connecting to Schwab...\n")

    try:
        client = SchwabClient()

        account_numbers = client.get_account_numbers()
        print(f"Found {len(account_numbers)} account(s).\n")

        accounts = client.get_accounts()
        for acct in accounts:
            print(f"Account: {acct.account_number}  Type: {acct.account_type}")
            print(f"  Cash balance:   ${acct.cash_balance:,.2f}")
            print(f"  Account value:  ${acct.account_value:,.2f}")

        for an in account_numbers:
            positions = client.get_positions(an.hash_value)
            orders = client.get_orders(an.hash_value)

            print(f"\nPositions ({an.account_number}):")
            if not positions:
                print("  (no positions)")
            for p in positions:
                print(f"  {p.ticker:6s}  qty={p.quantity:8.2f}  avg=${p.average_price:8.2f}  value=${p.market_value:10.2f}  pnl=${p.unrealized_pnl:+.2f}")

            print(f"\nOpen Orders ({an.account_number}):")
            if not orders:
                print("  (no open orders)")
            for o in orders:
                price_str = f"@ ${o.limit_price:.2f}" if o.limit_price else "(market)"
                print(f"  {o.order_id}  {o.action} {o.quantity} {o.ticker} {price_str}  [{o.status}]")

        print("\nOK Schwab connection verified.")

    except SchwabAuthError as e:
        print(f"\nFAIL Auth error: {e}")
        print("Run: poetry run python src/schwab/auth_setup.py")
    except SchwabAPIError as e:
        print(f"\nFAIL API error (status {e.status_code}): {e}")


if __name__ == "__main__":
    main()
