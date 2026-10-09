# API — usage `/api/usage/`

What a subscriber did in the last 30 days, what that says about the tariff or
pack that fits them, and the personal offer made on the back of it.

All numbers are computed by the backend from the catalogue and the usage rows;
no model is involved. In this prototype the usage rows come from seed data: the
backend is not connected to an operator network.

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `summary/?days=` | `ready` | Usage profile: totals, data by category and app, spend, segment |
| GET | `recommendations/` | `ready` | Ranked recommendations, insights and the open personal offer |
| POST | `offers/<id>/accept/` | `ready` | Buy the offered pack at the offer price |
| POST | `offers/<id>/decline/` | `ready` | Decline the offer |

## `GET summary/?days=30`

`days` is 1 to 90, 30 when left out.

```json
← 200 {
  "window": { "days": 30, "from": "2026-09-10", "to": "2026-10-09" },
  "segment": { "key": "heavy_data", "label": "Heavy internet user" },
  "headline": "23.4 GB, 60 min. and 10 SMS in 30 days; 32.98 ₼ paid",
  "totals": { "data_mb": 24000, "data_gb": "23.44", "minutes": 60, "sms": 10,
              "roaming_data_mb": 0, "roaming_minutes": 0, "roaming_days": 0 },
  "daily_average": { "data_mb": 800, "minutes": 2.0, "sms": 0.3 },
  "data_by_category": [ { "key": "video", "label": "Video", "data_mb": 14864, "share": 0.62 }, … ],
  "data_by_app": [ { "key": "youtube", "label": "YouTube", "category": "video", "data_mb": 14864, "share": 0.62 }, … ],
  "data_ran_out": { "day": 3, "date": "2026-09-21", "period_days": 28 },
  "spend": { "tariff_fee": "12.00",
             "addon_packs": { "count": 5, "amount": "20.98" },
             "roaming": { "count": 0, "amount": "0.00" },
             "other": "0.00", "total": "32.98" },
  "services": [ { "id": "missed-call", "name": "Buraxılmış zəng" } ]
}
```

- `segment.key` is one of `heavy_data`, `voice_only`, `roamer`, `balanced`,
  `low_usage`.
- Categories and their apps: `video` (youtube, kinon), `social`
  (instagram_facebook, tiktok), `messaging` (whatsapp, telegram), `games`
  (games, steam), `other` (teams, other).
- `data_ran_out` is the day of the current tariff period on which the included
  internet was used up, or `null`.
- `spend.tariff_fee` is the price of the tariff period, taken from the tariff
  record. Add-on packs and roaming are summed from wallet transactions.

## `GET recommendations/`

Always for the last 30 days.

```json
← 200 {
  "window_days": 30,
  "segment": { "key": "heavy_data", "label": "Heavy internet user" },
  "current_monthly_cost": "32.98",
  "fits": false,
  "message": "You paid 32.98 ₼ in the last 30 days; with High-volume 20 GB it would have been 27.00 ₼",
  "recommendations": [
    { "kind": "internet_pack", "target_id": "hv-20gb", "title": "High-volume 20 GB",
      "current_monthly_cost": "32.98", "projected_monthly_cost": "27.00", "saving": "5.98",
      "evidence": [ "5 add-on packs, 20.98 ₼", "Included internet ran out on day 3 of 28",
                    "YouTube 62% of data", "23.4 GB used in 30 days, tariff includes 5 GB" ],
      "action": { "action": "navigate", "to": "/internet-packs", "label": "Open internet packs" } },
    { "kind": "tariff_plan", "target_id": "digimax-25", … }
  ],
  "insights": [ { "category": "video", "share": 0.62, "text": "Video: 62% of your data",
                  "sells": [ { "kind": "social_pack", "target_id": "youtube", "title": "YouTube", "action": { … } }, … ] } ],
  "offer": null
}
```

- `kind` is `tariff_plan`, `internet_pack`, `social_pack` (with `plan_id`),
  `roaming_pack` (with `quantity` when more than one is needed) or `redesign`
  (with `values`, the IsteSen slider values).
- `current_monthly_cost` is what the subscriber paid: tariff fee, add-on packs
  and roaming. `projected_monthly_cost` is what the same 30 days would have
  cost with the recommendation.
- `fits: true` with an empty `recommendations` means nothing in the catalogue
  beats the current setup. This is a normal answer, not an error.
- An option that costs more than what was paid is recommended only when the
  included internet ran out before the period ended; its `saving` is negative.
- `insights[].sells` is empty when nothing in the catalogue answers that
  category (for example games).
- `offer` is the open personal offer or `null`. Returning it marks it `shown`.

```json
"offer": { "id": 9001, "kind": "social_pack", "target_id": "instagram-facebook:5gb",
           "title": "Instagram & Facebook 5 GB", "normal_price": "3.00", "offer_price": "2.00",
           "reason": "Instagram & Facebook is most of your internet: 5 GB for less",
           "status": "shown", "expires_at": "2026-10-23T08:00:00Z",
           "action": { "action": "navigate", "to": "/offers/9001", "label": "See the offer" } }
```

## `POST offers/<id>/accept/`

A money POST: `Idempotency-Key` is required. No body.

```json
← 201 { "offer": { …, "status": "accepted" },
        "activation": { "id": 12, "pack_id": "instagram-facebook", "label": "Instagram & Facebook 5 GB", "status": "active", "activated_at": "…", "expires_at": "…", "auto_renew": false },
        "transaction": { "id": 51, "title": "Instagram & Facebook 5 GB", "amount": "-2.00" },
        "balance": "14.21" }
← 402 { "code": "insufficient_balance", "detail": "Not enough balance for this pack" }
← 404 { "code": "not_found" }       // no such offer, or it belongs to someone else
← 409 { "code": "offer_closed", "detail": "This offer is no longer available" }
```

The pack is charged at the offer price and activated exactly as a normal
purchase. A tariff offer buys nothing, because a tariff at an offer price is not built:
it answers `200` with `{ "offer": …, "action": { navigate to the tariff } }`
and stays open.

## `POST offers/<id>/decline/`

```json
← 200 { "offer": { …, "status": "declined" } }
← 409 { "code": "offer_closed" }
```

No new offer is made for 7 days after a decline.

## Offer lifecycle

`new` → `shown` → `accepted` | `declined` | `expired`. A subscriber has at most
one open (`new` or `shown`) offer. Offers are created from rules staff define
in the admin by segment; a scheduled task applies them every 15 minutes and
writes a notification with `cta.deep_link` `/offers/<id>`.
