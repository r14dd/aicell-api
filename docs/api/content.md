# API — content `/api/content/`

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `home/` | `ready` | Home feed: story shelf (viewed last), quick actions, carousel banners, lottery banner |
| GET | `stories/` | `ready` | Shelf order with `viewed` flags |
| GET | `stories/<key>/` | `ready` | Story pages |
| POST | `stories/<key>/viewed/` | `ready` | Mark viewed (moves chip to the end) |
| GET | `banners/?placement=` | `ready` | `home`, `products`, `benefits`, `partners` |
| GET | `notifications/?q=&from=&to=` | `ready` | List with search and date range |
| GET | `notifications/<id>/` | `ready` | Detail (marks read) |
| POST | `notifications/<id>/read/` | `ready` | "Got it" |
| GET | `notifications/options/` | `:todo` | Header options menu |
| GET | `lottery/rules/` | `ready` | "Lottery rules & info" sections |
| GET | `lottery/chances/` | `:todo` | Chance balance (no screen) |
| GET | `lottery/terms/` | `:todo` | Terms link target |
| GET | `games/` | `ready` | Games, reward games, tournament |
| GET | `games/?q=` | `:todo` | Search |
| GET | `games/<slug>/launch/` | `:todo` | Portal launch URL |
| POST | `games/tournament/join/` | `:todo` | "Participate in the tournament" |
| GET | `games/tournament/rules/` | `:todo` | Rules |
| GET | `offers/apps/` | `ready` | Kinon, Yandex Plus, Litres |
| POST | `offers/apps/<id>/subscribe/` | `:todo` | |
| GET | `offers/aztelekom/` | `ready` | Fiber Optical card |
| POST | `offers/aztelekom/order/` | `:todo` | |
| GET | `perks/` | `ready` | Partner perks (Wingz, Wolt+) |
| GET | `campaigns/` | `ready` | Campaigns (Azercellim.com) |
| GET | `gift-wheel/` | `:todo` | Gift Wheel state |
| POST | `gift-wheel/spin/` | `:todo` | Spin |
| POST | `app-rating/` | `ready` | "Rate the app" stars |
| GET | `about/` | `:todo` | About Azercell |
| GET | `map/` | `:todo` | Stores map |
| GET | `stickers/` | `:todo` | Sticker packs |
| GET | `help/` | `:todo` | Help & Support |
| POST | `problem-report/` | `:todo` | Report a problem |

## `GET home/`

```json
← 200 {
  "stories": [ { "key": "gift-wheel", "label": "Gift Wheel", "image": "…/chip-gift-wheel.png", "viewed": false, "has_story": true }, … 7 … ],
  "quick_actions": [ { "key": "simkredit", "label": "SimKredit", "deep_link": "/kredit" }, { "key": "buy-internet", "label": "Buy internet", "deep_link": "/internet-packs" }, { "key": "sim-settings", "label": "SIM settings", "deep_link": "/sim-settings" } ],
  "banners": [ { "key": "akart", "image": "…", "alt": "Instant loan with akart! …", "deep_link": "/kredit/tamamla" }, { "key": "spin", "image": "…", "alt": "Spin the Gift Wheel! …", "deep_link": null }, … 10 … ],
  "lottery": { "title": "30 il səninlə", "subtitle": "Chance collection starts on 19 October 2026", "starts_at": "2026-10-19", "cta": "Learn more about the lottery", "deep_link": "/lottery-rules" }
}
```

`has_story=false` chips have no recorded story; the client shows its
notice. Today all seven have stories.

## `GET stories/<key>/`

```json
← 200 { "key": "especially", "title": "Especially for you", "thumb": "…", "pages": [ { …StoryPage JSON… }, … ], "next_key": "applications", "prev_key": "roaming" }
```

`pages[]` uses the `StoryPage` shape from `src/data/stories.ts`
verbatim; image fields are URLs instead of `require()` ids.

## `GET notifications/?q=wingz&from=2025-10-20&to=2025-10-31`

```json
← 200 { "results": [ { "id": "wingz", "title": "Activate Wingz scooter with your Azercell balance!", "body": "Get 15 minutes of free time …", "cta": null, "sent_at": "2025-10-27T09:00:00Z", "read": false } ], "next": null, "unread": 2 }
```

Empty `results` renders "No results". `unread` feeds the bell badge.

## `GET lottery/rules/`

```json
← 200 { "sections": [ { "icon": null, "title": "About the lottery", "blocks": [ { "kind": "p", "text": "We are launching …" }, … ] },
                      { "icon": "Diamond", "title": "How to earn chances?", "blocks": [ { "kind": "p", "num": "1.", "bold": "Top up your balance with 5 AZN or more", "text": "and get 1 chance …" }, { "kind": "example", "items": [ … ] }, … ] }, … 7 … ],
       "terms_url": null }
```

## `GET games/`

```json
← 200 { "games": [ { "id": "ninja-saga-2", "name": "Ninja Saga 2", "image": "…" }, … 8 … ],
       "reward_games": [ { "id": "battle-for-gb", "name": "Battle for GB", "image": "…" } ],
       "tournament": { "title": "Tournament", "game": "ninja-saga-2", "prize": "5 GB", "participants": 6708, "ends_at": "2026-10-08T15:17:02Z", "cta": "Participate in the tournament" } }
```

## `POST app-rating/`

```json
→ { "stars": 5 }
← 201 { "message": "Thanks! Your rating helps us a lot" }   // stars < 4 → "Thanks for the feedback, we will do better"
```

## `GET offers/apps/`, `GET offers/aztelekom/`, `GET perks/`, `GET campaigns/`

Return the lists in `src/data/mock.ts` (`appOffers`, `aztelekom`,
`partnerPerks`, `campaigns`) with image URLs and `deep_link: null`
(their detail pages are `:todo`).
