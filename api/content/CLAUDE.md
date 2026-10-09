# api/content

Home feed, stories, banners, notifications, lottery, games and partner offers. Docs: `docs/api/content.md`.

## Models
- Per subscriber: `StoryView` (which chips were viewed), `Notification` (public id is `slug`; translated), `AppRating`.
- Catalogue (`CatalogueItem`): `Story` → `StoryPage`, `QuickAction`, `Banner` (by `placement`), `LotterySection`, `Game` (not translated), `Tournament` → `Game`, `Offer` (by `kind`).

## Endpoints (`/api/content/`)
| Method | Path | Status |
|---|---|---|
| GET | `home/`, `stories/`, `stories/<key>/`, `banners/?placement=`, `notifications/?q=&from=&to=`, `notifications/<id>/`, `lottery/rules/`, `games/`, `offers/apps/`, `offers/aztelekom/`, `perks/`, `campaigns/` | ready |
| POST | `stories/<key>/viewed/`, `notifications/<id>/read/`, `app-rating/` | ready |
| GET | `notifications/options/`, `lottery/chances/`, `lottery/terms/`, `games/<slug>/launch/`, `games/tournament/rules/`, `gift-wheel/`, `about/`, `map/`, `stickers/`, `help/` | :todo |
| POST | `games/tournament/join/`, `offers/apps/<id>/subscribe/`, `offers/aztelekom/order/`, `gift-wheel/spin/`, `problem-report/` | :todo |

## Not obvious from the code
- `GET games/?q=` answers 501 (search is :todo) while `GET games/` is ready: one handler, `views.games`.
- Story shelf (`services.shelf`): unviewed chips in catalogue order, then viewed ones by `viewed_at`; viewing again moves a chip to the very end. `next_key` / `prev_key` follow catalogue order.
- `GET notifications/<id>/` marks the notification read, same as `POST .../read/`. `unread` in the list ignores the filters.
- `offers/apps/`, `offers/aztelekom/`, `perks/`, `campaigns/` are one factory (`views.offers(kind, ...)`) over `Offer.kind` app / aztelekom / perk / campaign.
- Image fields in models are file names; `with_images` turns them into absolute `/media/content/<name>` URLs after the cache. The files themselves are not in the repo.
- The lottery banner on `home/` and `LOTTERY_STARTS_AT` are in `views.py`, not in a model.
- `urls.py` order matters: `notifications/options/` and `games/tournament/...` come before the `<slug>` routes.

## Tests
`uv run pytest tests/test_content.py`; catalogue edits and cache: `tests/test_catalogue.py`.
