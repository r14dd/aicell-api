# white-collar-backend

Backend of the white-collar mobile app: a mobile operator's self-service API
with an admin panel. It implements the 115 endpoints of
[docs/api/](docs/api/overview.md) and answers in Azerbaijani, Russian and
English.

- [Run it](#run-it) · [Signing in](#signing-in) · [Languages](#languages) ·
  [Admin panel](#admin-panel)
- [Architecture](#architecture) · [Money](#money) · [Tests](#tests) ·
  [Operations](#operations)
- [Configuration](#configuration) · [Known limitations](#known-limitations)

## Run it

### With Docker

```sh
cp .env.example .env        # then set DJANGO_SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

One command brings up the API (gunicorn), PostgreSQL, Redis, a Celery worker
and Celery beat. The `web` service migrates, collects static files and seeds
before it starts serving.

| | |
|---|---|
| API | <http://localhost:8010/api/> |
| Swagger | <http://localhost:8010/api/swagger/> |
| Admin | <http://localhost:8010/admin/> |
| Health | <http://localhost:8010/api/health/ready/> |

Check the running system from the outside (every endpoint in three languages,
then a sign-in to the admin as each role):

```sh
python scripts/smoke.py http://localhost:8010 \
  --token "$(docker compose exec -T web python manage.py demo_token)"
```

### Without Docker

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.13 itself).
With `DATABASE_URL` and `REDIS_URL` unset it runs on SQLite and an in-memory
cache.

```sh
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py seed
uv run python manage.py runserver
```

`seed` loads the catalogue in three languages, the demo subscriber
`994516643342` and the four admin accounts. It is safe to run on every start:
rows that exist are kept, so edits made in the admin survive. `--refresh` puts
the seeded catalogue rows back to their initial content, `--reset` recreates
the demo subscriber.

## Signing in

`Authorization: Bearer <access-jwt>` for the app, `Token <key>` for services.
The app has no login screen yet and `users/otp/*` is `:todo`, so there are two
ways in:

- `manage.py demo_token` prints an access token for the demo subscriber
  (valid 30 days). Use it in Swagger's **Authorize** dialog.
- **`DEMO_AUTH=true`** makes every request *without* an `Authorization` header
  act as the demo subscriber, so the app works before login is built.

`DEMO_AUTH` is off by default and independent of `DJANGO_DEBUG`. Turning it on
lets anyone who can reach the server use that one account, which is fine for a
demo and nothing else. `.env.example` turns it on for local work; a public
deployment has to opt in knowingly.

## Languages

Send `Accept-Language: az`, `ru` or `en`. A missing header or an unsupported
language answers in `en`; the language used is returned in `Content-Language`.

What comes back translated: error messages (including the framework's own
validation messages), success messages, `:todo` notices and all catalogue copy.
What never changes with the language: `code` in errors, ids, prices.

- **Code strings** are in `locale/{az,ru}/LC_MESSAGES/django.po`.
  `manage.py sync_locale` updates the `.po` files from the code and compiles
  them (no GNU gettext needed); `--check` fails on a missing translation.
- **Catalogue rows** hold one column per language
  ([django-modeltranslation](https://django-modeltranslation.readthedocs.io/)),
  edited in the admin in three tabs.

A receipt is written in the language of the purchase and stays that way.

## Admin panel

`/admin/`, built with [django-unfold](https://unfoldadmin.com/). `seed` creates
one account per role; the password is `SEED_STAFF_PASSWORD`
(`white-collar-demo` unless set). A password changed later is kept.

| Login | Role | Can |
|---|---|---|
| `superadmin` | Superadmin | everything |
| `content` | Content manager | add, change, delete the catalogue and notifications |
| `support` | Support | view subscribers and what they did |
| `finance` | Finance | view billing |

Each role sees only its own menu and dashboard figures; a page outside its
permissions answers `403`. Transactions, top-ups and idempotency keys are
read-only for everyone, the superadmin included: money changes only through
the API.

## Endpoint status

| Status | Meaning |
|---|---|
| `ready` | Implemented and tested. |
| `:todo` | Routed at its final path, answers `501 not_implemented` with a notice text. |
| `:dummy` | The assistant: works end to end, answers come from a keyword responder. |

`/api/health/` and `/api/health/ready/` are extra to the documented 115.

## Architecture

One package per domain, the same layers in each:

```
urls.py  ->  views.py  ->  services.py   ->  models.py
                      \->  catalogue.py  ->  models.py
                      \->  texts.py
```

| Layer | Owns | Never does |
|---|---|---|
| `views.py` | parsing input, calling a service, shaping JSON, its Swagger entry | business rules, wallet writes |
| `services.py` | the rules: charging, activating, limits, "all wins" | anything with requests or responses |
| `catalogue.py` | reading catalogue rows into the documented shapes, cached | subscriber data |
| `texts.py` | fixed screen copy, translated through `.po` files | |
| `models.py` | state, and the catalogue rows editors manage | |

Three rules hold the design together:

- **Money moves in one place.** Every balance change goes through
  `billing.services.move`, which writes the transaction in the same database
  transaction. Packs, SIM services and Steam all charge through it.
- **A handler describes itself once.** `@doc(...)` next to a handler gives its
  summary, typed input and error codes; `route()` turns that into the view,
  its permissions, its limits and its Swagger entry.
- **The catalogue lives in the database.** The API never reads the seed files;
  they only fill the tables the first time.

`tests/test_architecture.py` checks these layers on the import graph, so a
view-to-view import or a service that reaches for the request fails the build.

```
config/            settings, celery, admin menu
api/common/        errors, auth, routing, schema, throttling, cache, health, admin bases
api/<domain>/      urls, views, services, catalogue, texts, models, translation, admin, tasks
api/seeding/       initial catalogue (data/), translations, demo subscriber, admin roles
locale/            az and ru message catalogues
docs/api/          the API reference this backend follows
scripts/smoke.py   end-to-end check of a running deployment
tests/
```

## Money

- Every balance change runs in one database transaction and locks the
  subscriber's wallet row first (`select_for_update`). The check against the
  balance and the write happen under that lock, so parallel requests cannot
  take a balance below zero.
- Every `POST` that moves money needs `Idempotency-Key: <uuid>`. The key is
  stored in the same transaction as the charge. Repeating a request with the
  same key returns the first answer and charges nothing, also when the two
  arrive at the same moment.
- "Only once" rules (a service or an auto-renewing pack that is already
  active) are checked under the same lock.

## Tests

```sh
uv run pytest                  # SQLite; PostgreSQL and Redis tests are skipped
uv run ruff check . && uv run ruff format --check .
```

With PostgreSQL and Redis from Compose, the whole suite runs, including the
parallel-request tests:

```sh
docker compose up -d db redis
DATABASE_URL=postgres://white_collar:<POSTGRES_PASSWORD>@127.0.0.1:54329/white_collar \
REDIS_URL=redis://127.0.0.1:63799/15 \
uv run pytest
```

Use a Redis database of its own for tests (`/15` above): they clear it.

| File | What it proves |
|---|---|
| `test_docs_conformance.py` | every row of the endpoint tables in `docs/api/*.md` exists and behaves as marked |
| `test_isolation.py` | with two subscribers: no read leaks, no write crosses over, foreign ids are `404`, no token is `401` |
| `test_robustness.py` | malformed bodies, queries and content types never produce a `500` |
| `test_concurrency.py` | PostgreSQL only: parallel purchases, parallel top-ups, the same key twice at once |
| `test_languages.py` | every read in az/ru/en; nothing left untranslated in code or catalogue |
| `test_swagger.py` | the schema is valid with warnings as errors; recorded examples match live answers |
| `test_admin.py` | every model's pages open; each role sees exactly its share; money is read-only |
| `test_catalogue.py` | admin edits reach the API; the cache is per language and dropped on change |
| `test_throttling.py`, `test_health.py`, `test_security.py` | limits, probes, deployment settings |
| `test_architecture.py` | the layering rules above |

## Operations

**Health.** `GET /api/health/` says the process is up and checks nothing.
`GET /api/health/ready/` checks the database, Redis and the Celery broker and
reports each; `503` when one fails. Both are open, uncached, unthrottled and
ignore `Accept-Language`. A component without configuration (a local run
without Redis) is `not_configured` and does not fail the probe.

**Limits.** Counted in the cache. A `429` carries `Retry-After`.

| Scope | Default | Applies to |
|---|---|---|
| `THROTTLE_OTP_IP`, `THROTTLE_OTP_PHONE` | `5/min` | `otp/*`, per address and per number |
| `THROTTLE_MONEY` | `30/min` | money-moving `POST`s, per subscriber |
| `THROTTLE_SUBSCRIBER` | `300/min` | everything else, per subscriber |

An empty value switches a limit off. Behind a proxy the per-address limit sees
the proxy's address unless DRF's `NUM_PROXIES` is set for it.

**Cache.** Catalogue answers are cached per language. Saving or deleting any
catalogue row, in the admin or anywhere else, drops the whole catalogue cache.
Nothing that belongs to a subscriber is cached.

**Scheduled work** (Celery beat): expired packs are switched off every minute;
idempotency keys older than `IDEMPOTENCY_KEY_DAYS` are deleted hourly.

**Swagger.** Response schemas and examples come from
`api/common/examples.json`, recorded from the real answers by
`manage.py record_examples` (it runs in a transaction that is rolled back).
Run it after changing what an endpoint returns; a test fails if you forget.

## Configuration

Everything is read from the environment; `.env` is loaded if present.

| Variable | Default | |
|---|---|---|
| `DJANGO_DEBUG` | `false` | |
| `DJANGO_SECRET_KEY` | none | required when debug is off: the server refuses to start without it |
| `DJANGO_ALLOWED_HOSTS` | none (`localhost,127.0.0.1` in debug) | comma-separated |
| `CORS_ALLOWED_ORIGINS` | none | used when debug is off; in debug every origin is allowed |
| `CSRF_TRUSTED_ORIGINS` | none | origins the admin is served from |
| `SECURE_SSL_REDIRECT`, `SECURE_COOKIES` | `true` | set both `false` only for plain-HTTP local runs |
| `SECURE_HSTS_SECONDS` | `31536000` | |
| `DATABASE_URL` | SQLite file | `postgres://…` in Docker |
| `REDIS_URL` | none (in-memory cache, tasks run inline) | cache, limits, Celery broker |
| `DEMO_AUTH` | `false` | see [Signing in](#signing-in) |
| `GOOGLE_PAY_SIMULATED` | follows `DJANGO_DEBUG` | accept `payment_token: "simulated"` |
| `SEED_STAFF_PASSWORD` | `white-collar-demo` | change it anywhere public |
| `THROTTLE_*` | see Limits | |
| `CATALOGUE_CACHE_SECONDS` | `300` | |
| `ASSISTANT_RESPONDER` | `api.assistant.responder.respond` | |

With debug off, cookies are secure-only, HSTS is on, plain HTTP is redirected
(except the health probes) and `X-Forwarded-Proto` from the proxy is trusted.
`manage.py check --deploy` passes without warnings in that configuration.

**Deliberate exceptions in `docker-compose.yml`.** Compose serves plain HTTP on
localhost, so it sets `SECURE_SSL_REDIRECT=false` and `SECURE_COOKIES=false`.
`check --deploy` then reports exactly three warnings: `W008`, `W012`, `W016`.
Behind TLS, remove both overrides.

## Known limitations

- **The assistant calls no model.** It routes on keywords and answers in
  English. `ASSISTANT_RESPONDER` names the callable, so a model-backed
  responder with the same signature replaces it without touching the views.
- **Placeholder content.** The docs abbreviate long lists with `…` and point to
  the mobile app's `src/data/*.ts`, which is not part of this repository. Those
  entries were written in the documented shape and are now ordinary catalogue
  rows: three of the seven story chips and all story pages, eight of the ten
  home banners, five of the seven lottery sections, seven of the eight games,
  the offer lists, the tariff plan features, most internet packs, two of the
  three SIM services and seven of the eight Premium benefits.
- **Translations were written for this prototype**, not taken from the
  operator's approved copy. Product names are kept as they are.
- **Notice texts.** `:todo` answers should carry the app's own toast text. Only
  the ones quoted in the docs are exact; the rest follow the same pattern.
- **Images.** Image fields are absolute URLs under `/media/content/`; the image
  files are not in the repository.
- **The admin's own labels are English.** Django's and Unfold's built-in
  interface follows the browser language.

## Where this differs from the docs

The docs disagree with themselves in three places; the server takes one side:

| Docs | Server |
|---|---|
| `top-ups/` lists ids as `"h01"`, `top-up/card/` returns `"id": 16` | integer ids everywhere |
| `my/usage/` shows `data_total_gb: "20"`, `my/` shows a 16 GB total | `"16"`, from the same row as `my/` |
| `renewal_label` says `00:00`, "Next payment date" says `08:00+04:00` | the label follows the payment date: `08:00` |

Shapes the docs leave open were chosen here: `stories/` and `internet/top/`
return `{ "results": [...] }`, `POST stories/<key>/viewed/` returns
`{ "key", "viewed": true }`, and the JSON form of an assistant turn returns
`{ "user_message_id", "message", "action" }`.

## Built with

Django 5.2, Django REST Framework, SimpleJWT, drf-spectacular, django-unfold,
django-modeltranslation, Celery, Redis, PostgreSQL, gunicorn, WhiteNoise,
pytest. Data is synthetic. No external model is called.
