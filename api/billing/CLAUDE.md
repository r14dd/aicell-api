# api/billing

The wallet and everything that moves money. Docs: `docs/api/billing.md`.

## Models
- `Wallet` — one per subscriber, holds `balance`. Created lazily by `services.balance_of` / `lock_wallet`.
- `Transaction` — every balance change; `amount` is signed; `kind` top_up / purchase / payment / credit.
- `TopUp`, `SteamTopUp` (each 1:1 `Transaction`), `SavedCard`, `SavedAkart`, `SteamAccount`; `IdempotencyKey` — stored reply of a money POST, unique per (subscriber, key).

## Endpoints (`/api/billing/`)
| Method | Path | Status |
|---|---|---|
| GET | `balance/`, `transactions/`, `top-ups/`, `top-up/methods/`, `cards/`, `steam/accounts/` | ready |
| POST | `top-up/card/`, `top-up/akart/`, `top-up/google-pay/`, `steam/top-up/` | ready, money |
| POST | `top-up/voucher/`, `cards/`, `pay/number/`, `pay/aztelekom/`, `pay/utilities/` | :todo |
| GET | `akart/`, `payments/` | :todo |
| DELETE | `cards/<id>/`, `steam/accounts/<id>/` | :todo |

## Not obvious from the code
- `services.move(subscriber, signed_amount, kind=, title=)` is the only place the balance changes: it locks the wallet row (`select_for_update`), checks, writes, and creates the `Transaction`. `charge()` is `move` with a negative amount. Other domains call these.
- `lock_wallet` doubles as the per-subscriber mutex for "only once" rules (used in `api/packs/services.py`, `api/sim/services.py`).
- `@idempotent` (`idempotency.py`) wraps the handler and the key insert in one `transaction.atomic`. Only 2xx replies are stored; a failed attempt can be retried with the same key. A key reused on another path is 400. The handler must return `(body, status)`.
- Replies are stored as JSON: on PostgreSQL (jsonb) a replayed body has reordered keys. Bodies must hold plain strings (services use non-lazy `gettext`); `Transaction.title` keeps the language of the request.
- `top_ups_this_month` uses the Asia/Baku month; `top-ups/?from=&to=` are inclusive Baku dates. Google Pay: only `payment_token == "simulated"` with `GOOGLE_PAY_SIMULATED` on completes; anything else is 501.
- `presenters.py` (`transaction_brief`, `top_up_receipt`) is shared with packs. `tasks.purge_idempotency_keys` runs hourly (beat), cutoff `IDEMPOTENCY_KEY_DAYS`.
- Admin: `Wallet`, `Transaction`, `TopUp`, `SteamTopUp`, `IdempotencyKey` are read-only for everyone.

## Tests
`uv run pytest tests/test_billing.py tests/test_conventions.py`; races: `tests/test_concurrency.py` (PostgreSQL only).
