# API — kredit `/api/kredit/`

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `` (root) | `ready` | Get Kredit page: debt + products |
| GET | `products/<slug>/` | `ready` | SimKredit / SimTaksit / InternetKredit / EkstraKredit detail |
| POST | `products/<slug>/take/` | `:todo` | "Get <product> X ₼" |
| GET | `tamamla/` | `ready` | Tamamla page: banner, steps, akart link |

## `GET /api/kredit/`

```json
← 200 {
  "debt": { "amount": "0.00", "note": "no items", "items": [] },
  "products": [
    { "id": "simkredit",      "name": "SimKredit",      "subtitle": "Get now! Pay back at the next topup",            "chip": "1-3 ₼",  "chip_icon": "coins",     "deep_link": "/kredit/simkredit" },
    { "id": "simtaksit",      "name": "SimTaksit",      "subtitle": "Get now! Pay back within 32 days by 0.08 ₼",     "chip": "2 ₼",    "chip_icon": "coins",     "deep_link": "/kredit/simtaksit" },
    { "id": "internetkredit", "name": "InternetKredit", "subtitle": "Get now! Pay back at the next topup",            "chip": "300 MB", "chip_icon": "broadcast", "price": "2 ₼", "deep_link": "/kredit/internetkredit" },
    { "id": "ekstrakredit",   "name": "EkstraKredit",   "subtitle": "Get now! Pay back at the next topup",            "chip": "1 ₼",    "chip_icon": "coins",     "deep_link": "/kredit/ekstrakredit" }
  ]
}
```

## `GET products/<slug>/`

```json
← 200 { "id": "simtaksit", "name": "SimTaksit", "amount": "2.00", "fee": "0.60", "unit": "₼",
       "options": ["1", "2", "3"],            // simkredit only
       "amount_mb": 300, "validity_days": 7,  // internetkredit only
       "cta": "Get SimTaksit 2.00 ₼" }
```

## `POST products/<slug>/take/` `:todo`

```json
→ { "amount": "2.00" }
← 501 { "code": "not_implemented", "detail": "SimTaksit 2.00 ₼ will be added to your balance (prototype)" }
```

When built: creates `CreditDebt`, credits the wallet (`kind=credit`,
title "<name> credit") or, for InternetKredit, a 300 MB / 7-day
`PackActivation`.

## `GET tamamla/`

```json
← 200 { "banner": { "image": "…/tamamla-hero.png", "alt": "Instant loan with akart! Complete your payments up to 50 ₼ with akart loan" },
       "steps": [ "Apply for akart with ease: …", "Give permission to borrow up to 50.00 ₼ …", "Activate Tamamla & Cover unexpected expenses!" ],
       "cta": { "label": "Get now!", "url": "https://links.akart.az/app/" } }
```
