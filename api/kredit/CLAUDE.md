# api/kredit

Credit products (SimKredit, SimTaksit, InternetKredit, EkstraKredit) and the subscriber's debt. Docs: `docs/api/kredit.md`.

## Models
- `CreditDebt` — an open or repaid credit of a subscriber (`repaid_at` null = open).
- `KreditProduct` — catalogue (`CatalogueItem`; `subtitle` and `chip` translated, `name` is a brand and is not).

## Endpoints (`/api/kredit/`)
| Method | Path | Status |
|---|---|---|
| GET | `` (root), `products/<slug>/`, `tamamla/` | ready |
| POST | `products/<slug>/take/` | :todo |

## Not obvious from the code
- Nothing creates `CreditDebt` yet (`take/` is :todo), so `debt` is always `0.00` / "no items" unless rows are added in the admin.
- `take/` is a `Todo` whose notice is computed by `views.take_notice`: it echoes the requested `amount` and still answers 404 for an unknown slug. When built it should create `CreditDebt` and credit the wallet via `billing.services.move(kind="credit")`, or a `PackActivation(kind="kredit")` for a data product.
- `products/<slug>/` adds `options`, `amount_mb`, `validity_days` only when the product has them.
- The root list adds `price` only when `price_label` is set; `deep_link` is derived as `/kredit/<slug>`.
- `catalogue.products()` is one cached list serving both the root and the detail endpoint.
- `tamamla/` copy lives in `views.py` as translated strings, not in a model.
- No `services.py`: the domain has no write rules yet.

## Tests
`uv run pytest tests/test_products.py -k "kredit or tamamla"`
