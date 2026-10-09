# API — tariffs `/api/tariffs/`

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `catalogue/` | `ready` | All families with plans (Change tariff, catalogue pages) |
| GET | `catalogue/<family>/` | `ready` | One family; `?plan=` selects the chip |
| GET | `hot/` | `ready` | "Hot offers on tariffs" cards (Products) |
| POST | `subscribe/` | `ready` | "Subscribe for X ₼" on a catalogue page |
| GET | `my/` | `ready` | IsteSen page: header, usage, payment details, total price, banner, charging note |
| GET | `my/usage/` | `ready` | Home "Remaining balance" card, Remaining balance page, aggregation sheet copy |
| POST | `my/renew/` | `ready` | Renew tariff sheet → Renew |
| GET | `my/redesign/` | `ready` | Slider config + current estimate |
| POST | `my/redesign/` | `ready` | "Save: 19.10 ₼" |
| GET | `change/` | `ready` | Change tariff groups and cards |
| POST | `change/` | `ready` | Choose a card without a family page |
| GET | `premium/` | `ready` | Premium benefits + note |
| POST | `premium/activate/` | `:todo` | Premium "Continue" |

## `GET catalogue/<family>/?plan=digimax-25`

```json
← 200 {
  "id": "digimax", "name": "DigiMax", "subtitle": null, "badges": ["PREPAID"], "is_premium": false,
  "selected_plan": "digimax-25",
  "plans": [
    { "id": "digimax-5",  "title": "DigiMax 5GB",  "price": "12.00", "hot": false,
      "features": [ { "kind": "internet", "label": "Internet", "value": "5 GB" }, … ] },
    { "id": "digimax-10", "title": "DigiMax 10GB", "price": "18.00", "hot": true,  "features": [ … ] },
    { "id": "digimax-25", "title": "DigiMax 25GB", "price": "30.00", "hot": true,  "features": [ … ] }
  ],
  "total_price": [
    { "heading": "When you use all package, prices will be next:", "tone": "secondary",
      "rows": [ { "label": "Internet - 1MB", "price": "0.05" }, … ] },
    { "heading": "If monthly fee is not paid:", "tone": "red", "rows": [ … ] }
  ],
  "note": "When the subscription fee of the tariff is paid, the line of the number will remain bilaterally active for 28 days.",
  "cta": "Subscribe for 30.00 ₼"
}
```

Features keep the `kind` enum of `src/data/tariffs.ts`
(`internet|calls|sms|social|app|roaming|validity`) and an optional
`socials` list.

## `GET hot/`

Returns `hotTariffs` from `src/data/mock.ts` in frame order
(`digimax-10`, `premium-60`, `digimax-25`) with `socials` and `features`
(`data|minutes|sms|roaming`).

## `GET my/`

```json
← 200 {
  "family": "istesen", "title": "IsteSen", "pills": ["CURRENT TARIFF", "PREPAID"],
  "lines": [ { "label": "Current tariff", "value": "19.10 ₼/month" }, { "label": "Next renewal", "value": "19.10 ₼/month" } ],
  "usage": [
    { "kind": "internet",  "label": "Internet",    "remaining": "7.20", "remaining_unit": "GB",  "total": "16", "total_unit": "GB",  "ratio": 0.45 },
    { "kind": "messaging", "label": "Messaging",   "remaining": "1003", "remaining_unit": "MB",  "total": "1",  "total_unit": "GB",  "ratio": 0.98 },
    { "kind": "calls",     "label": "Local calls", "remaining": "30",   "remaining_unit": "MIN.", "total": "30", "total_unit": "MIN.", "ratio": 1 }
  ],
  "payment_details": [
    { "label": "Validity period", "value": "30 d." },
    { "label": "Activation date", "value": "2026-09-24T00:00:00+04:00" },
    { "label": "Last payment date", "value": "2026-09-24T00:00:00+04:00" },
    { "label": "Next payment date", "value": "2026-10-25T08:00:00+04:00" },
    { "label": "Payment amount", "value": "19.10" }
  ],
  "total_price": [ …two groups of four rows… ],
  "charging_note": "Charging interval: 1 minute for calls",
  "banner": { "image": "…/banner-want-more.png", "alt": "All you need and more!", "deep_link": "/internet-packs" },
  "renew": { "title": "Renew tariff", "body": "By renewing tariff, the remaining balance will be annulled but the existing old internet packs will still stay active." }
}
```

## `GET my/usage/`

```json
← 200 {
  "tariff": "IsteSen", "renewal_label": "Renews 25 October, 00:00", "period_left": { "days": 18, "hours": 21 },
  "remaining": { "data_gb": "7.20", "data_total_gb": "16", "minutes": 30, "minutes_total": 30 },
  "rows": [ …same three usage rows… ],
  "aggregation": [
    { "title": "For internet", "body": "<copy of the Balances aggregation sheet>" },
    { "title": "For calls",    "body": "<copy>" }
  ]
}
```

`remaining.data_gb` and `remaining.data_total_gb` are the tariff plus every
active internet pack with a fixed size (the sum the aggregation sheet
describes): with a 5 GB pack active the example becomes `"12.20"` of `"21"`.
`rows` stay the tariff alone.

## `GET my/redesign/`

```json
← 200 { "sliders": [
  { "key": "internet",    "label": "Internet GB",       "min": 0,  "max": 16,  "step": 1,  "value": 16 },
  { "key": "calls",       "label": "Local calls min.",  "min": 30, "max": 350, "step": 10, "value": 30 },
  { "key": "instagramFb", "label": "Instagram & FB GB", "min": 0,  "max": 5,   "step": 1,  "value": 0 },
  { "key": "youtube",     "label": "YouTube GB",        "min": 0,  "max": 10,  "step": 1,  "value": 0 },
  { "key": "tiktok",      "label": "TikTok GB",         "min": 0,  "max": 10,  "step": 1,  "value": 0 }
], "pricing": { "base": "19.10", "per_gb": "0.50", "per_minute": "0.02" }, "estimate": "19.10" }
```

The client computes the live estimate with `pricing`.

## `POST my/redesign/`

```json
→ { "values": { "internet": 10, "calls": 100, "instagramFb": 5, "youtube": 2, "tiktok": 0 } }
← 200 { …the body of GET my/redesign/ with the saved values and estimate… }
```

Every slider key is required; a value outside `min`..`max` or off `step` is
`400` with `errors.values.<key>`. Nothing is charged: the saved values set
the price and amounts of the next renewal ("Next renewal" in `GET my/`).
Only the IsteSen tariff can be redesigned (`400` otherwise).

## `GET change/`

Returns `changeGroups` from `src/data/myTariff.ts`: two groups
(`digimax`, `premium`), each card with `price` (range string), `period`,
`tagline`, `is_new`, `socials`, `features`, and `family_id` when a
catalogue page exists (`digimax`, `premium-plus`) else `null`.

## `GET premium/`

```json
← 200 { "logo": "…/premium-logo.png",
  "benefits": [ { "key": "curator", "text": "Personal curator for all your needs" }, … 8 items … ],
  "note": "To access the Premium theme you must log in with Premium number as main account" }
```

## `POST subscribe/`, `POST change/`, `POST my/renew/`

Money endpoints: an `Idempotency-Key` header (UUID) is required, as on every
purchase.

```json
→ subscribe/   { "plan_id": "digimax-5" }
→ change/      { "tariff_id": "digimax-3gb" }
→ my/renew/    {}
← 201 {
  "tariff": { "family": "digimax", "plan_id": "digimax-5", "title": "DigiMax 5GB", "price": "12.00",
              "validity_days": 28, "activated_at": "2026-10-09T16:40:00+04:00",
              "next_payment_at": "2026-11-06T16:40:00+04:00" },
  "transaction": { "id": 81, "title": "DigiMax 5GB tariff", "amount": "-12.00" },
  "balance": "4.21"
}
```

- All three charge the wallet and start a full period: remaining amounts are
  back to the total, what was left of the old period is annulled, active packs
  stay. `402 insufficient_balance` changes nothing.
- `subscribe/` takes a plan of `catalogue/`; `change/` takes a card whose
  `family_id` is `null` (a card with a page is `400`: use `subscribe/`).
  The tariff the subscriber already has is `409 already_active`: renew it.
- `my/renew/` pays the "Next renewal" price. IsteSen renews with its saved
  slider values, a plan at its current catalogue price. `plan_id` is `null`
  for IsteSen.

## `:todo` writes

`premium/activate/` `{}` returns `501` with the app's notice text until built.
