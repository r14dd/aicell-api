# tests

pytest + pytest-django. Settings: `tests/settings.py` (debug off, no `.env`, in-memory cache, eager Celery). All tests go through HTTP.

## Fixtures (`conftest.py`)
- `catalogue` seeds the catalogue; `subscriber` adds the demo subscriber `994516643342` (balance 16.21).
- `other` / `other_client` — a second subscriber (`994500000002`, balance 99.99) for isolation checks.
- `client` — signed in as `subscriber` via `force_authenticate`; `anon` — no credentials. `client_for(user)` builds more.
- `client.pay(path, body, key=None)` sends a money POST with an `Idempotency-Key`; `post_json`, `patch_json`. One file: `uv run pytest tests/test_sim.py`.
- Autouse: `DEMO_AUTH` off, every throttle rate off, stream delay 0, cache cleared before and after each test.

## Files
| File | Covers |
|---|---|
| `test_docs_conformance.py` | parses `docs/api/*.md`; exports `ROWS` (115) reused by other files |
| `test_billing.py`, `test_sim.py`, `test_content.py`, `test_assistant.py` | one domain each |
| `test_products.py` | tariffs, packs, kredit, referral |
| `test_conventions.py` | auth, error shape, idempotency |
| `test_isolation.py`, `test_robustness.py` | two-subscriber leaks; malformed input never 500 |
| `test_concurrency.py` | parallel money requests; PostgreSQL only |
| `test_languages.py`, `test_catalogue.py`, `test_swagger.py`, `test_admin.py` | az/ru/en; DB catalogue + cache + tasks; OpenAPI; admin and roles |
| `test_throttling.py`, `test_health.py`, `test_security.py`, `test_architecture.py` | limits; probes; settings via subprocess; import layering |

## Not obvious
- On SQLite 10 tests skip (8 `postgres`, 2 `redis`). Full run: `docker compose up -d db redis`, then `DATABASE_URL=postgres://white_collar:<POSTGRES_PASSWORD from .env>@127.0.0.1:54329/white_collar REDIS_URL=redis://127.0.0.1:63799/15 uv run pytest`. Use Redis db `/15`: tests flush it.
- Counts are asserted: 115 doc rows (`test_docs_conformance.py`), 116 operations (`test_swagger.py`), 23 catalogue models (`test_catalogue.py`). Update them when adding endpoints or models.
- `test_swagger.py` compares live answers with `api/common/examples.json` by shape; after changing a response run `uv run python manage.py record_examples`.
- A throttle test must set its own rates (`limits(settings, money="3/min")`); a concurrency test needs `django_db(transaction=True)` and its own DB connection per thread (`in_parallel`).
- English strings are asserted literally in many tests, and `test_languages.py` runs `sync_locale --check`: changing or adding copy means updating tests and both `.po` files.
