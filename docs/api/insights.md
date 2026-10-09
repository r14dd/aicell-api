# API — insights `/api/insights/`

What a subscriber's own numbers show, found by rules, each with priced answers
from the live catalogue. The backend writes no sentences: `evidence` holds the
facts and `offers` the arithmetic, and whoever shows the insight (the
assistant, a card, a notification) words it. Nothing here calls a model.

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/` | `ready` | Insights that may be shown now, urgent first |
| POST | `<id>/seen/` | `ready` | The app showed it |
| POST | `<id>/accept/` | `ready` | The subscriber said yes; returns the offer's task |
| POST | `<id>/dismiss/` | `ready` | The subscriber said no; the kind is silent for 14 days |
| GET | `advisor/` | `ready` | The tariff setup that fits the usage ("IsteSen+") |

## Where the figures come from

| Source | Used for |
|---|---|
| `usage.DailyUsage`, `usage.AppUsage` | data per day and per app, minutes, roaming, out-of-package traffic |
| `tariffs.SubscriberTariff` | remaining and included internet, price, renewal date, slider values |
| `packs.PackActivation` with its `billing.Transaction` | add-on packs bought and what they cost |
| `billing.Wallet`, `billing.SavedCard` | balance; whether a card is saved |

Usage rows are seed data in this prototype (see [usage.md](usage.md)); the
detectors are real rules over them.

Derived figures (`api/insights/metrics.py`):

| Figure | How |
|---|---|
| `burn` | average home data per day, last 7 days |
| `days_left` | time to `next_payment_at` |
| `days_to_empty` | remaining internet ÷ `burn` |
| `gap` | `burn × days_left − remaining` (positive: it will not last) |
| `video_share`, `social_share` | YouTube + TikTok, and Instagram & Facebook, as a share of 30 days of data |
| per month | the last 60 days scaled to 30, or as many days as there is history |
| `monthly_spend` | tariff price + add-on packs per month + out-of-package charges per month |
| finished periods | usage in each of the last three periods of the tariff's length, against what it includes |

## Detectors

Offers are chosen from the catalogue tables at run time (`api/insights/catalogue.py`),
ranked by price and price per gigabyte; a pack added or repriced in the admin
is picked up without a code change. Thresholds are constants in
`api/insights/detectors.py`.

| `kind` | Fires when | `evidence` | Offers | Severity |
|---|---|---|---|---|
| `overage` | the tariff's internet is 0, more than a day is left and over 20 MB were charged per megabyte today | `overage_mb`, `overage_amount`, `rate_per_mb`, `burn_gb_day`, `days_left` | the cheapest day pack; the cheapest pack that covers the days left | `urgent` |
| `renewal_shortfall` | the renewal is within 2 days and costs more than the balance | `balance`, `price`, `shortfall`, `renews_at`, `has_card` | a top-up of the shortfall rounded up to a manat; SimKredit when no card is saved | `urgent` |
| `video_heavy` | a general pack of 5 GB or more was used up within 3 days and video is 60% of the data | `pack{id, data_gb, price, per_gb, activated_at, emptied_at, days}`, `by_app_gb`, `video_share` | the YouTube / TikTok plan sized to that usage, with what the same gigabytes cost in the general pack | `info` |
| `repeat_packs` | 2 or more add-on packs in the current tariff period | `packs[]`, `packs_total`, `tariff_price`, `monthly_spend`, `data_gb_month` | the cheapest plan that holds the monthly usage, then the next one up | `info` |
| `forecast_gap` | 70% of the tariff's internet is used and `gap` is positive | `remaining_gb`, `days_left`, `burn_gb_day`, `empty_on`, `gap_gb`, `need_gb` | the cheapest pack holding `gap × 1.1` (one that lasts the days in question, if any); the biggest pack that costs less | `info` |
| `social_heavy` | Instagram & Facebook is 40% of the data, or TikTok is 4 GB a month | `by_app_gb`, `social_share`, `tiktok_gb_month` | IsteSen slider values fitted to the usage (IsteSen only); the app's own plan from 1 GB a month | `info` |
| `underused` | half or more of the included internet was left in each of the last 3 periods | `included_gb`, `periods[]{start, end, used_gb, unused_gb}` | IsteSen with less internet (IsteSen only); a cheaper plan that still holds the busiest period | `info` |
| `roaming` | roaming data in the last 3 days and no roaming pack running | `roaming_mb`, `days` | the two roaming packs with the cheapest gigabyte | `info` |

An offer dearer than what is paid now is only made by `repeat_packs`,
`overage` and `forecast_gap`; its `saving` is then `null`.

## `GET /`

The detectors run on every call, so a purchase or a top-up is reflected by
the next one; a nightly task (`manage.py insights`) runs them for everyone.

```json
← 200 {
  "results": [{
    "id": 7001, "kind": "social_heavy", "severity": "info", "status": "new",
    "created_at": "2026-10-09T16:20:00+04:00", "expires_at": "2026-10-16T16:20:00+04:00",
    "evidence": {
      "by_app_gb": { "instagram_facebook": 7.0, "other": 2.4, "tiktok": 0.6, "whatsapp": 0.8, "youtube": 1.9 },
      "social_share": 0.55, "tiktok_gb_month": 0.6
    },
    "offers": [
      { "ref": "redesign", "label": "IsteSen+", "price": "18.10", "validity": null,
        "data_gb": 14.0, "per_gb": null, "saving": "1.00", "saving_year": "12.00",
        "values": { "instagramFb": 5, "youtube": 2, "tiktok": 1, "internet": 6, "calls": 30 },
        "task": { "name": "applyRedesign", "params": { "instagramFb": 5, "youtube": 2, "tiktok": 1, "internet": 6, "calls": 30 } } },
      { "ref": "social:instagram-facebook:5gb", "label": "Instagram & Facebook 5 GB", "price": "3.00",
        "validity": "30 d.", "data_gb": 5.0, "per_gb": "0.60", "saving": null,
        "task": { "name": "activatePack", "params": { "slug": "instagram-facebook", "plan": "5gb" } } }
    ],
    "recommended": 0
  }]
}
```

- `label` and `validity` are in the `Accept-Language` language; everything
  else is numbers and keys. `recommended` is an index into `offers`.
- An offer whose catalogue item was switched off is left out; an insight with
  no offer left is not returned.
- `evidence` has the same fields for a `kind` every time (the table above).

**Delivery policy** (decided on the server, the same for every client):

- nothing between 23:00 and 08:00 Asia/Baku (`INSIGHTS_QUIET_HOURS=false` switches this off);
- every `urgent` insight; at most one new `info` insight per 48 hours (the
  one being shown keeps coming back until it is answered or lapses);
- an insight lapses 7 days after it was written (`expired`);
- there is never a second open insight of a kind: the open one gets the new
  figures. When its condition no longer holds it is closed as `resolved`.

### Tasks

`task` says what carrying out the offer means. It is done with the endpoint
that owns the action; nothing in this domain moves money.

| `task.name` | `params` | Endpoint |
|---|---|---|
| `buyPack` | `kind` (`internet` or `roaming`), `pack_id` | `POST packs/internet/purchase/` or `packs/roaming/purchase/` `{ "pack_id" }` |
| `activatePack` | `slug`, `plan` | `POST packs/social/<slug>/activate/` `{ "plan_id": plan }` |
| `changeTariff` | `plan` | `POST tariffs/subscribe/` `{ "plan_id": plan }` |
| `applyRedesign` | the slider values | `POST tariffs/my/redesign/` `{ "values": params }` |
| `topUp` | `amount` | `POST billing/top-up/card/` (or another top-up method) |
| `takeKredit` | `slug` | `POST kredit/products/<slug>/take/` (`:todo`) |

## `POST <id>/seen/`, `POST <id>/accept/`, `POST <id>/dismiss/`

```json
→ accept/  { "offer": 1 }        // optional; the recommended offer when left out
← 200 { …the insight, "status": "accepted"…, "task": { "name": "activatePack", "params": { … } } }
```

- `seen/` moves `new` to `seen`. `accept/` and `dismiss/` close the insight;
  answering it again changes nothing and returns it as it is.
- After `dismiss/` no insight of that kind is written for 14 days; after
  `accept/` for 2 days, so the purchase has time to happen.
- `accept/` charges nothing. An `offer` outside the list is `400`; someone
  else's insight is `404`.

## `GET advisor/`

What a month costs now against the setups that would fit the usage.
"IsteSen+" is not a tariff of its own: it is the IsteSen constructor with
slider values worked out from the usage and priced with the constructor's
formula (`tariffs/my/redesign/` `pricing`).

```json
← 200 {
  "period_days": 30,
  "profile": { "data_gb_month": 12.7,
               "by_app_gb": { "instagram_facebook": 7.0, "other": 2.4, "tiktok": 0.6, "whatsapp": 0.8, "youtube": 1.9 },
               "minutes_month": 20 },
  "current": { "tariff": "IsteSen", "price": "19.10", "packs_month": "0.00", "total_month": "19.10" },
  "candidates": [
    { "id": "istesen-plus", "title": "IsteSen+", "price": "18.10", "total_month": "18.10",
      "saving_month": "1.00", "saving_year": "12.00", "data_gb": 14, "minutes": 30,
      "redesign": { "instagramFb": 5, "youtube": 2, "tiktok": 1, "internet": 6, "calls": 30 },
      "task": { "name": "applyRedesign", "params": { "instagramFb": 5, "youtube": 2, "tiktok": 1, "internet": 6, "calls": 30 } } },
    { "id": "digimax-25", "title": "DigiMax 25GB", "price": "30.00", "total_month": "30.00",
      "saving_month": "-10.90", "data_gb": 25, "minutes": 500,
      "task": { "name": "changeTariff", "params": { "plan": "digimax-25" } } },
    { "id": "premium-60", "title": "Premium+ 60GB", "price": "60.00", "total_month": "60.00",
      "saving_month": "-40.90", "data_gb": 60, "minutes": null, "rejected": "usage_x4.7", "task": { … } }
  ],
  "recommended": "istesen-plus",
  "effective_from": "2026-10-25"
}
```

| Step | How |
|---|---|
| Profile | data per app and minutes per month (60 days of history, or what there is) |
| Current | tariff price + add-on packs per month |
| IsteSen+ | each app slider = that app's monthly GB, rounded up and kept in range; what an app uses beyond its slider goes to general internet; general internet = the rest × 1.3; messaging fits the 1 GB every tariff includes. `rejected: "does_not_cover"` when general internet would need more than its slider allows. Only for a subscriber on IsteSen |
| Nearest plan | the cheapest catalogue plan that holds the monthly data |
| Next plan up | listed only with `rejected: "usage_x<n>"`, when it holds at least twice the usage |
| `recommended` | the lowest `total_month` among candidates that are not rejected; `"current"` when it saves less than 1 ₼ |

`effective_from` is the next renewal: a redesign is applied by `tariffs/my/renew/`.
`404` when the subscriber has no tariff.
