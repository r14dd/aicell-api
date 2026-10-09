# API — billing `/api/billing/`

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `balance/` | `ready` | Balance and this month's top-up sum (Home) |
| GET | `transactions/` | `ready` | Recent transactions (Home "Recent transactions", Payments "Recent payments") |
| GET | `top-ups/` | `ready` | Top-up history with date range (Top-ups page) |
| GET | `top-up/methods/` | `ready` | Methods list for "Select a top-up method" |
| POST | `top-up/card/` | `ready` | Bank card top-up (BIN + amount) |
| POST | `top-up/akart/` | `ready` | akart top-up (+ save number) |
| POST | `top-up/voucher/` | `:todo` | 13-digit voucher |
| POST | `top-up/google-pay/` | `ready` | Google Pay (simulated token accepted in DEBUG) |
| GET | `akart/` | `:todo` | Saved akart numbers |
| GET | `cards/` | `ready` | Saved cards (Payments tab) |
| POST | `cards/` | `:todo` | Add card |
| DELETE | `cards/<id>/` | `:todo` | Remove card (card settings) |
| GET | `payments/` | `:todo` | Payment history (Payments → History) |
| POST | `pay/number/` | `:todo` | Top up another Azercell number |
| POST | `pay/aztelekom/` | `:todo` | Aztelekom home internet payment |
| POST | `pay/utilities/` | `:todo` | Electricity, gas, water |
| GET | `steam/accounts/` | `ready` | Saved Steam accounts |
| POST | `steam/top-up/` | `ready` | Pay a Steam account from the balance |
| DELETE | `steam/accounts/<id>/` | `:todo` | Remove a saved account |

Every `POST` that moves money requires `Idempotency-Key` and returns the
new `balance`.

## `GET balance/`

```json
← 200 { "balance": "16.21", "currency": "AZN", "top_ups_this_month": "16.00", "month": "2026-10" }
```

## `GET transactions/`

```json
← 200 { "results": [
  { "id": 42, "kind": "purchase", "title": "Unlimited 1 hour pack", "amount": "-0.99", "created_at": "2026-10-08T09:12:00Z" },
  { "id": 2,  "kind": "top_up",   "title": "Number balance",        "amount": "15.00", "created_at": "2026-10-02T12:39:00Z" },
  { "id": 1,  "kind": "top_up",   "title": "Number balance",        "amount": "1.00",  "created_at": "2026-10-02T12:34:00Z" }
], "next": null }
```

## `GET top-ups/?from=2026-10-02&to=2026-10-06`

Inclusive dates in `Asia/Baku`. Without a range: all, newest first.

```json
← 200 { "results": [
  { "id": "h01", "amount": "15.00", "method": "card", "created_at": "2026-10-02T12:39:00Z" },
  { "id": "h02", "amount": "1.00",  "method": "card", "created_at": "2026-10-02T12:34:00Z" }
], "next": null }
```

## `GET top-up/methods/`

```json
← 200 { "banner": { "image": "…/banner-akart.png", "alt": "Instant loan with akart! …", "deep_link": "/kredit/tamamla" },
  "methods": [
    { "key": "card",    "label": "Top up from bank card", "deep_link": "/top-up/card" },
    { "key": "akart",   "label": "akart",                 "deep_link": "/top-up/akart" },
    { "key": "voucher", "label": "Voucher",               "deep_link": "/top-up/voucher" },
    { "key": "kredit",  "label": "Get Kredit",            "deep_link": "/kredit" }
  ],
  "google_pay": { "available": true, "min": "1.00", "max": "500.00", "note": "We don't charge any fees for Google Pay top-ups" } }
```

## `POST top-up/card/`

```json
→ { "card_bin": "416300", "amount": "25.00" }
← 201 { "top_up": { "id": 16, "method": "card", "amount": "25.00", "status": "completed", "created_at": "…" },
       "transaction": { "id": 43, "title": "Number balance", "amount": "25.00" },
       "balance": "41.21" }
```

Validation: `card_bin` 6 digits, `amount` `1.00`–`500.00`.

## `POST top-up/akart/`

```json
→ { "akart_msisdn": "994516643342", "amount": "20.00", "save": true }
← 201 { …same as card…, "saved_akart": { "id": 3, "msisdn": "994516643342" } }
```

## `POST top-up/voucher/` `:todo`

```json
→ { "code": "1234567890123" }
← 501 { "code": "not_implemented", "detail": "Voucher redemption is not part of this prototype yet" }
```

## `POST top-up/google-pay/`

```json
→ { "amount": "20.00", "payment_token": "simulated", "card_last4": "4471" }
← 201 { …same as card with "method": "google_pay"… }
```

In DEBUG `payment_token == "simulated"` completes immediately (the app's
`GooglePaySheet`). Real token verification is `# TODO(acquirer)`.

## `GET cards/`

```json
← 200 { "results": [ { "id": 1, "brand": "mastercard", "last4": "4471", "expiry": "09/28", "is_default": true } ] }
```

## `GET steam/accounts/`

```json
← 200 { "results": [ { "id": 5, "name": "gamer_01", "last_amount": "10.00", "last_topped_at": "2026-10-08T09:00:00Z" } ],
       "limits": { "min": "1.00", "max": "50.00" }, "chips": ["5", "10", "25", "50"] }
```

## `POST steam/top-up/`

```json
→ { "account": "gamer_01", "amount": "10.00", "save": true }
← 201 { "steam_top_up": { "id": 9, "account": "gamer_01", "amount": "10.00" },
       "transaction": { "id": 44, "title": "Steam balance gamer_01", "amount": "-10.00" },
       "balance": "6.21" }
← 402 { "code": "insufficient_balance", "detail": "Not enough balance for this top-up" }
← 400 { "code": "validation_error", "detail": "Enter an amount between 1.00 and 50.00 ₼" }
```
