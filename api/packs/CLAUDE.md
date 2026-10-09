# api/packs

Internet, social and roaming packs and their activations. Docs: `docs/api/packs.md`.

## Models
- `PackActivation` — a bought pack: `kind` internet / social / roaming / kredit, `pack_id` (catalogue slug, not an FK), `status`, `expires_at`, 1:1 `billing.Transaction`.
- Catalogue (`CatalogueItem`, translated): `PackCategory` → `InternetPack`; `SocialPack` → `SocialPlan`; `RoamingPack`.

## Endpoints (`/api/packs/`)
| Method | Path | Status |
|---|---|---|
| GET | `internet/`, `internet/top/`, `social/<slug>/`, `roaming/` | ready |
| POST | `internet/purchase/`, `social/<slug>/activate/`, `roaming/purchase/` | ready, money |
| GET | `active/` | :todo |

## Not obvious from the code
- Each purchase in `services.py` charges through `billing.services.charge` and creates the `PackActivation` in one transaction; the view adds `@idempotent`.
- Only `SocialPack.auto_renew` packs are single-instance: a second activation while one is active and unexpired is 409, checked under `billing.lock_wallet`. Internet and roaming packs stack.
- `PackActivation.label` and the transaction title are stored in the request language ("Unlimited 1 hour pack" / "Limitsiz 1 saat paketi").
- An unknown `pack_id` / `plan_id` in the body is 400; an unknown `<slug>` in the path is 404. Inactive rows (`is_active=False`) count as unknown.
- `internet/` → `packs` is keyed by category slug and omits categories without packs (the `social` category has none by design).
- `internet/top/` lists `InternetPack` rows with `top_position` set.
- `social/<slug>/` builds `rows` and `default_plan` from the pack's first plan; a pack without plans is 404.
- `InternetPack.hours` / `SocialPlan.days` / `RoamingPack.days` set `expires_at` and are never returned.
- `tasks.expire_activations` (beat, every minute) flips `status` to `expired` once `expires_at` passes.
- `PackActivation` is read-only in the admin.

## Tests
`uv run pytest tests/test_products.py -k "internet or social or roaming"`; races: `tests/test_concurrency.py`; expiry task: `tests/test_catalogue.py`.
