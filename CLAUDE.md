# white-collar-backend

Django 5.2 + DRF 3.18 backend of a mobile operator app: 115 endpoints (`docs/api/*.md`), django-unfold admin, az/ru/en.
Python 3.13, uv, drf-spectacular, simplejwt, django-modeltranslation, Celery + Redis, PostgreSQL (SQLite when `DATABASE_URL` is unset).

## Commands
- Install: `uv sync` · run: `uv run python manage.py runserver` (reads `.env`; copy `.env.example`)
- Migrations: `uv run python manage.py makemigrations` / `migrate`
- Seed: `uv run python manage.py seed` (`--reset` demo subscriber, `--refresh` seeded catalogue rows)
- Tests: `uv run pytest` (settings `tests/settings.py`) · lint: `uv run ruff check . && uv run ruff format .`
- Translations: `uv run python manage.py sync_locale` (updates `.po`, compiles `.mo`; `--check` verifies)
- Swagger examples: `uv run python manage.py record_examples` · token: `uv run python manage.py demo_token`
- Docker: `docker compose up --build` → API `:8010`, PostgreSQL `:54329`, Redis `:63799`
- Live check: `python scripts/smoke.py http://localhost:8010 --token <demo_token>`

## Map
- `config/` settings (`settings.py`, `env.py`), `celery.py`, admin menu (`unfold.py`)
- `api/common/` errors, auth, routing, schema, throttling, cache, health, admin bases, management commands
- `api/users/` subscriber account (the auth user model), sign-in stubs
- `api/billing/` wallet, transactions, top-ups, cards, Steam, idempotency keys
- `api/tariffs/` tariff catalogue and the subscriber's tariff
- `api/packs/` internet, social and roaming packs and their activations
- `api/kredit/` credit products and debts
- `api/sim/` SIM settings and paid services
- `api/content/` home feed, stories, banners, notifications, lottery, games, offers
- `api/referral/` invite & earn
- `api/assistant/` support conversations with a keyword responder
- `api/seeding/` seed data (`data/`), its translations, demo subscriber, admin roles
- `locale/` az and ru `.po`/`.mo` · `templates/admin/index.html` dashboard · `tests/`

## Request path
`config/urls.py` → `api/urls.py` → `api/<domain>/urls.py` → `views.py` handler → `services.py` (rules) or `catalogue.py` (cached reads) → `models.py`.
A handler is a plain function `(request, **url_kwargs)` returning a body, `(body, status)` or a response; `route()` in `api/common/routing.py` wraps it into the view.

## Rules for every domain
- Errors: raise `ApiError` subclasses from `api/common/exceptions.py`; body is `{code, detail}` (+ `errors` on 400). Never build error responses by hand.
- Auth: default is authenticated. `Bearer` JWT, `Token`, or `DEMO_AUTH=true` (header-less requests act as subscriber `994516643342`; off by default).
- Isolation: filter every query by `request.user`; another subscriber's object answers 404.
- Language: `Accept-Language` az/ru/en (default en) via `api/common/middleware.py`. Wrap user-facing strings in `gettext_lazy` in views/texts, `gettext` in services; then run `sync_locale` and fill the new `msgstr` in both `.po` files.
- `:todo` endpoint: `Todo(notice, summary)` in `route()`; answers 501. Keep it until implemented.
- Money: only through `api/billing/services.py` (`move`/`charge`); money POSTs carry `@idempotent` (`api/billing/idempotency.py`) and need `Idempotency-Key`.
- Layering is enforced by `tests/test_architecture.py`: nothing below views imports HTTP; no cross-domain view imports; views never touch `Wallet`.

## Do not change
Endpoint paths and response shapes are the contract in `docs/api/*.md`; `tests/test_docs_conformance.py` checks every table row (115). `README.md` is for people: leave it.

## Recipes
- New endpoint: handler with `@doc(...)` in `api/<domain>/views.py` → `route()` at the file's end → `api/<domain>/urls.py` → row in `docs/api/<domain>.md` (bump the count in `tests/test_docs_conformance.py` and `tests/test_swagger.py`) → `record_examples`.
- New translated string: `_()` in code → `sync_locale` → edit `locale/az/LC_MESSAGES/django.po` and `locale/ru/...` → `sync_locale`.
- New catalogue model: subclass `CatalogueItem` (`api/common/models.py`) → `translation.py` → reader in `catalogue.py` with `@cached` → `admin.py` (`CatalogueAdmin`) → menu entry in `config/unfold.py` → seed in `api/seeding/catalogue.py` + texts in `api/seeding/data/translations.py`.
- New admin model: `api/<domain>/admin.py` (bases in `api/common/admin.py`) → `config/unfold.py` `MENU` → role lists in `api/seeding/staff.py`.
- New Celery task: `api/<domain>/tasks.py` (`@shared_task` calling a service) → `CELERY_BEAT_SCHEDULE` in `config/settings.py`.
