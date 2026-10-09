# API — tariffs `/api/tariffs/`

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `catalogue/` | `ready` | All families with plans (Change tariff, catalogue pages) |
| GET | `catalogue/<family>/` | `ready` | One family; `?plan=` selects the chip |
| GET | `hot/` | `ready` | "Hot offers on tariffs" cards (Products) |
| POST | `subscribe/` | `:todo` | "Subscribe for X ₼" on a catalogue page |
| GET | `my/` | `ready` | IsteSen page: header, usage, payment details, total price, banner, charging note |
| GET | `my/usage/` | `ready` | Home "Remaining balance" card, Remaining balance page, aggregation sheet copy |
| POST | `my/renew/` | `:todo` | Renew tariff sheet → Renew |
| GET | `my/redesign/` | `ready` | Slider config + current estimate |
| POST | `my/redesign/` | `:todo` | "Save: 19.10 ₼" |
| GET | `change/` | `ready` | Change tariff groups and cards |
| POST | `change/` | `:todo` | Choose a card without a family page |
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
  "remaining": { "data_gb": "7.20", "data_total_gb": "20", "minutes": 30, "minutes_total": 30 },
  "rows": [ …same three usage rows… ],
  "aggregation": [
    { "title": "For internet", "body": "<copy of the Balances aggregation sheet>" },
    { "title": "For calls",    "body": "<copy>" }
  ]
}
```

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

The client computes the live estimate with `pricing`; `POST my/redesign/`
`:todo` takes `{ "values": { "internet": 16, … } }`.

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

## `:todo` writes

`subscribe/` `{ "plan_id": "digimax-25" }`, `my/renew/` `{}`,
`my/redesign/` `{ "values": {…} }`, `change/` `{ "tariff_id": "digimax-3gb" }`,
`premium/activate/` `{}` — all return `501` with the app's notice text
until built. `subscribe/`, `renew/` and `change/` will charge the wallet
and replace `SubscriberTariff`.
