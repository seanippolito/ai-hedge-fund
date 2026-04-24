# Notification System Design — Phase 2

**Date:** 2026-04-23
**Status:** Approved

---

## Goal

Run the AI Hedge Fund agent pipeline on a schedule and deliver stock recommendations to the user via email and Discord. Two notification types: hourly strong-signal alerts during market hours, and a daily digest at market close. Weekend digests run once each morning.

---

## Architecture

A new `src/notifications/` module owns all notification logic. A standalone entry point `scripts/scheduler.py` runs as a long-lived process (locally or as a systemd service on a VPS). The FastAPI web app is not involved.

```
scripts/scheduler.py              ← entry point: load .env, start scheduler, block
src/notifications/
    __init__.py
    scheduler.py                  ← APScheduler setup, job definitions, market-hours logic
    runner.py                     ← assemble tickers, invoke run_hedge_fund(), filter signals
    formatter.py                  ← render brief summary + full digest (plain text + HTML)
    senders/
        __init__.py
        email.py                  ← smtplib, Gmail SMTP
        discord.py                ← requests.post to Discord incoming webhook
tests/notifications/
    __init__.py
    test_runner.py
    test_formatter.py
    test_senders.py
```

Each component has a single responsibility and a clean interface. The scheduler only calls functions from `runner.py` — it knows nothing about formatting or delivery. This means the scheduler can be swapped for Temporal or Celery later by replacing `scheduler.py` alone.

---

## Schedule

All times are US/Eastern. APScheduler is initialised with `timezone=ZoneInfo("America/New_York")` so cron expressions are defined in ET and DST is handled automatically. This ensures correct behaviour regardless of the machine's local timezone (PST, UTC, or any other).

| Job | Cron | Days | Behaviour |
|-----|------|------|-----------|
| Hourly alert | `hour="8-17", minute=0` | Mon–Fri | Sends only if a strong signal is found |
| Weekday digest | `hour=18, minute=0` | Mon–Fri | Always sends |
| Weekend digest | `hour=DIGEST_HOUR_ET, minute=0` | Sat–Sun | Always sends, uses last available market data |

`DIGEST_HOUR_ET` defaults to `9` (9:00 AM ET) and is overridable via env var.

The 6 PM weekday digest captures after-hours moves and futures opens that occur after the final 5 PM hourly alert.

---

## Runner

`runner.py` is responsible for two things: building the ticker list and invoking the pipeline.

**Ticker assembly** — union of live Schwab holdings and a fixed watchlist:

```python
def get_tickers(client: SchwabClient) -> list[str]:
    accounts = client.get_accounts()
    holding_tickers = {
        pos.ticker
        for acct in accounts
        for pos in client.get_positions(acct.account_hash)
    }
    watchlist = {
        t.strip().upper()
        for t in os.environ.get("WATCHLIST", "").split(",")
        if t.strip()
    }
    return sorted(holding_tickers | watchlist)
```

If Schwab is unavailable, the runner logs the error and falls back to the watchlist only — it does not abort the run. If both Schwab and the watchlist produce zero tickers, the job logs a warning and skips the run.

**Pipeline invocation** — calls `run_hedge_fund()` from `src/main.py` directly:

```python
result = run_hedge_fund(
    tickers=tickers,
    start_date=today,
    end_date=today,
    portfolio={"cash": 0, "positions": {}, "margin_requirement": 0},
    model_name=os.environ["SCHEDULED_MODEL"],
    model_provider=os.environ["SCHEDULED_PROVIDER"],
    selected_analysts=os.environ.get("SCHEDULED_ANALYSTS", "warren_buffett").split(","),
)
```

**Strong signal filter** — used by the hourly alert job only:

```python
CONFIDENCE_THRESHOLD = int(os.environ.get("ALERT_CONFIDENCE_THRESHOLD", "70"))

def has_strong_signal(signals: dict) -> bool:
    return any(
        s["confidence"] >= CONFIDENCE_THRESHOLD and s["signal"] != "neutral"
        for ticker_signals in signals.values()
        for s in ticker_signals.values()
    )
```

---

## Notification Format

Both job types use the same two-part format: a scannable summary at the top, full reasoning below. The formatter produces both a plain-text version (Discord) and an HTML version (email).

**Hourly Alert:**
```
MARKET ALERT — Wed Apr 23, 2:00 PM ET

BULLISH  > AAPL 82%   INTC 71%
BEARISH  > DIS  76%

--- Full Analysis ---

AAPL — Bullish (82%)  [Warren Buffett]
Strong free cash flow and durable brand moat. Trading at modest
discount to intrinsic value given current rate environment.

INTC — Bullish (71%)  [Warren Buffett]
Recovery thesis intact. Foundry business undervalued relative to
peers despite near-term margin pressure.

DIS — Bearish (76%)  [Warren Buffett]
Streaming losses offsetting parks recovery. Valuation still
elevated given earnings uncertainty.
```

**Daily Digest** — same format but includes all tickers (neutral signals too), plus a footer with the Schwab account snapshot (total cash, total account value).

Weekend digests use the same digest format with a header noting that market data is from the last trading day.

---

## Delivery

### Email (Gmail SMTP)
Uses Python's built-in `smtplib` with `STARTTLS`. The HTML version is sent as a `multipart/alternative` message with a plain-text fallback.

### Discord (Incoming Webhook)
A `POST` to `DISCORD_WEBHOOK_URL` with `{"content": plain_text_message}`. For the digest, an embed is used to structure the summary and detail sections.

Both channels are optional — if the relevant env vars are absent, that channel is silently skipped. Both channels are attempted independently; a failure in one does not block the other.

---

## Error Handling

Each scheduled job is wrapped in a `try/except` that logs the error and returns without crashing the scheduler process. A failed run is logged at `ERROR` level and skipped — the next scheduled run will attempt normally.

Within a run, Schwab API failures fall back to watchlist-only tickers. Notification delivery failures (email or Discord) are caught independently per channel.

No retries on failed runs — the hourly cadence is the retry mechanism.

---

## Configuration

All configuration lives in `.env`. New variables for Phase 2:

```
# Tickers
WATCHLIST=AAPL,MSFT,NVDA,INTC

# Agent config
SCHEDULED_ANALYSTS=warren_buffett        # comma-separated, add more later
SCHEDULED_MODEL=claude-sonnet-4-6
SCHEDULED_PROVIDER=Anthropic
ALERT_CONFIDENCE_THRESHOLD=70            # minimum confidence to trigger alert

# Schedule
DIGEST_HOUR_ET=9                         # weekend digest hour (ET, 24h)

# Email (Gmail)
NOTIFICATION_EMAIL_FROM=you@gmail.com
NOTIFICATION_EMAIL_PASSWORD=your-gmail-app-password
NOTIFICATION_EMAIL_TO=you@gmail.com

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## Testing

All components are unit-testable without real API calls:

- `test_runner.py` — mock `SchwabClient` and `run_hedge_fund`, verify ticker union logic and signal filter
- `test_formatter.py` — pass synthetic signal dicts, assert plain-text and HTML output structure
- `test_senders.py` — mock `smtplib.SMTP` and `requests.post`, assert correct payloads sent

No integration tests required for Phase 2 — manual verification via `scripts/check_schwab.py` and a test Discord/email send covers end-to-end.

---

## Future Extensibility

The clean separation between scheduler, runner, formatter, and senders makes these upgrades straightforward later:

- **More analysts** — add to `SCHEDULED_ANALYSTS` env var, no code changes
- **Temporal/Celery** — replace `src/notifications/scheduler.py` only; runner and senders unchanged
- **Trade approval workflows** — add an approval step between runner and senders; Discord message includes approve/reject buttons via Discord interactions
- **Audit trail** — runner writes each signal result to the existing SQLAlchemy database before notifying
- **More channels** — add `senders/sms.py` (Twilio) following the same interface
