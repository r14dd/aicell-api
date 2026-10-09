# API — packs `/api/packs/`

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `internet/` | `ready` | Internet packs page: promo, categories, packs, social cards |
| GET | `internet/top/` | `ready` | Products "TOP internet packs" (three) |
| GET | `social/<slug>/` | `ready` | Social pack detail with plans |
| POST | `internet/purchase/` | `ready` | "Confirm your payment" → Confirm |
| POST | `social/<slug>/activate/` | `ready` | "Activate for X ₼" / "Subscribe for X ₼" |
| GET | `roaming/` | `ready` | Roaming packs list (Roaming page) |
| POST | `roaming/purchase/` | `ready` | "Yes, activate the pack" |
| GET | `active/` | `:todo` | Active activations (no screen yet) |

## `GET internet/`

```json
← 200 {
  "promo": { "title": "Unlimited entertainment is waiting for you!", "sub": "For only 0.99 ₼", "gradient": ["#8C80FE", "#4670E2"] },
  "categories": [ { "id": "unlimited", "label": "Unlimited" }, { "id": "high-volume", "label": "High-volume" }, { "id": "weekly", "label": "Weekly" }, { "id": "daily", "label": "Daily" }, { "id": "social", "label": "Social" } ],
  "packs": {
    "unlimited":   [ { "id": "unlimited-1h", "name": "1 hour", "sub": "Unlimited speed", "price": "0.99", "renews": false, "label": "Unlimited 1 hour" }, … ],
    "high-volume": [ … ], "weekly": [ … ], "daily": [ … ]
  },
  "social": [
    { "id": "tehsil", "title": "Tehsil", "subtitle": "Join online classes with ease via Microsoft Teams.", "app": "teams",
      "range": "0.7-9.9", "special": false, "volume": "10-100 GB", "periods": ["Daily", "Monthly"], "cta": "Subscribe", "auto_renew": true },
    { "id": "instagram-facebook", …, "special": true, "cta": "Activate" }, { "id": "tiktok", … }, { "id": "youtube", … }
  ],
  "msisdn": "994516643342"
}
```

`msisdn` is the "For number" line on the confirmation sheet.

## `POST internet/purchase/`

```json
→ { "pack_id": "unlimited-1h" }
← 201 { "activation": { "id": 11, "pack_id": "unlimited-1h", "label": "Unlimited 1 hour", "status": "active",
                        "activated_at": "…", "expires_at": "…", "auto_renew": false },
       "transaction": { "id": 45, "title": "Unlimited 1 hour pack", "amount": "-0.99" },
       "balance": "15.22" }
← 402 { "code": "insufficient_balance", "detail": "Not enough balance for this pack" }
```

## `GET social/<slug>/`

```json
← 200 { "id": "tehsil", "title": "Tehsil", "app": "teams", "badge": "AUTO-RENEWAL",
  "rows": [ { "label": "Application traffic", "value": "10 GB" }, { "label": "Validity period", "value": "1 d." }, { "label": "Renews", "value": "Automatically" } ],
  "note": "<lilac note copy>",
  "plans": [ { "id": "10gb", "title": "10 GB", "price": "0.70", "validity": "1 d." }, { "id": "100gb", "title": "100 GB", "price": "9.90", "validity": "30 d." } ],
  "default_plan": "10gb", "cta": "Subscribe" }
```

`rows` change with the selected plan on the client (volume and validity
come from the plan).

## `POST social/<slug>/activate/`

```json
→ { "plan_id": "100gb" }
← 201 { "activation": { … "label": "Tehsil 100 GB", "auto_renew": true }, "transaction": { "title": "Tehsil 100 GB", "amount": "-9.90" }, "balance": "6.31" }
```

## `GET roaming/`

```json
← 200 { "results": [ { "id": "r-500mb", "name": "500 MB", "sub": "3 days", "price": "10.00" }, { "id": "r-2gb", "name": "2 GB", "sub": "10 days", "price": "25.00" }, … ],
  "confirm": { "title": "You are not yet in the roaming area", "body": "Roaming internet pack is activated immediately after purchasing. Are you sure you want to proceed?", "decline": "No, thanks", "confirm": "Yes, activate the pack" } }
```

## `POST roaming/purchase/`

```json
→ { "pack_id": "r-2gb" }
← 201 { "activation": { … "label": "Roaming 2 GB" }, "transaction": { "title": "Roaming 2 GB pack", "amount": "-25.00" }, "balance": "…" }
```
