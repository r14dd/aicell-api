# api/tariffs

The tariff catalogue and the subscriber's own tariff. Docs: `docs/api/tariffs.md`.

## Models
- `SubscriberTariff` — one per subscriber: price, payment dates, remaining data/messaging/minutes, `redesign` slider values (JSON).
- Catalogue (`CatalogueItem`, translated): `TariffFamily` → `TariffPlan`; `PriceGroup` ("Total price" blocks); `ChangeGroup` → `ChangeCard` (optional FK to `TariffFamily`); `PremiumBenefit`; `RedesignSlider`.

## Endpoints (`/api/tariffs/`)
| Method | Path | Status |
|---|---|---|
| GET | `catalogue/`, `catalogue/<family>/?plan=`, `hot/`, `change/`, `premium/` | ready, catalogue |
| GET | `my/`, `my/usage/`, `my/redesign/` | ready, subscriber |
| POST | `subscribe/`, `my/renew/`, `my/redesign/`, `change/`, `premium/activate/` | :todo |

## Not obvious from the code
- No endpoint writes `SubscriberTariff`: its values come from `api/seeding/subscriber.py` only. Nothing here touches the balance.
- `hot/` lists plans with `hot_position` set (ordered by it) and uses `hot_socials` / `hot_features`, not `features`.
- The selected plan without `?plan=` is the one with `is_default`, else the first; an unknown `?plan=` is 400, an unknown family 404.
- `services.REDESIGN_PRICING` / `REDESIGN_INCLUDED` are code constants; `estimate()` = base + per-GB × (GB beyond 16 + social GB) + per-minute × (minutes beyond 30). "Next renewal" in `my/` is that estimate.
- `services.renewal_day` formats with `"j E"` so Russian gets the genitive month; do not change to `"F"`.
- `my/` payment dates use `iso_local` (+04:00), unlike the UTC `Z` used elsewhere.
- `my/usage/` returns `data_total_gb` from the model (16); `docs/api/tariffs.md` shows 20 (known doc inconsistency, see README).
- `catalogue.py` readers are `@cached` per language; views add fixed copy from `texts.py` after the cache.
- JSON fields (`features`, `rows`, `hot_features`) are translated per language as whole values (`features_az` …).

## Tests
`uv run pytest tests/test_products.py -k "tariff or catalogue or redesign or usage or premium or hot"`; cache/admin edits: `tests/test_catalogue.py`.
