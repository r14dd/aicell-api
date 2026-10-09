# api/referral

Invite & earn: the subscriber's code and the rules. Docs: `docs/api/referral.md`.

## Models
- `ReferralProfile` — one per subscriber: `code` (unique) and `earned`.
- `ReferralStep` — catalogue (`CatalogueItem`, translated): the ordered rules shown on the page.

## Endpoints (`/api/referral/`)
| Method | Path | Status |
|---|---|---|
| GET | `me/` | ready |
| GET | `terms/` | :todo |
| POST | `events/` | :todo |

## Not obvious from the code
- `earned` never changes yet: `events/` (the webhook that would credit a referral) is :todo. When built, `qualified` should credit the referrer through `billing.services.move(kind="credit", title="Referral bonus")` and bump `earned`.
- `events/` is meant for service accounts (`Authorization: Token <key>`), but currently has the default subscriber permission like every other route.
- `share_url` is built from `SHARE_URL` in `views.py`; `headline` and `share_message` are translated strings in `views.py`, the steps come from `catalogue.steps()` (cached).
- The 3.00 ₼ bonus appears in three places that must agree: the `headline` string in `views.py`, the step text in `api/seeding/data/referral.py` (`BONUS`) and its translations in `api/seeding/data/translations.py`.
- A subscriber without a `ReferralProfile` gets 404 from `me/`.
- No `services.py`: the domain has no write rules yet.

## Tests
`uv run pytest tests/test_products.py -k referral`
