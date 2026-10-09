# aicell-api

Backend API for the aicell mobile app, a mobile operator's self-service
product: balance and top-ups, tariffs, packs, credit, SIM settings, a support
assistant, and an admin panel for the people who run it. Built on Django and
Django REST framework. The mobile client lives in a separate repository.

The API follows the endpoint tables in [docs/api](docs/api/overview.md) and
answers in Azerbaijani, Russian and English. [docs/mobile-integration.md](docs/mobile-integration.md)
is the guide for wiring a client to it (in Azerbaijani).

## Run it

### Docker

```sh
cp .env.example .env     # set DJANGO_SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

This starts the API (gunicorn), PostgreSQL, Redis, a Celery worker and Celery
beat. The `web` container migrates, collects static files and seeds before it
serves.

| | |
|---|---|
| API | <http://localhost:8010/api/> |
| Swagger | <http://localhost:8010/api/swagger/> |
| Admin | <http://localhost:8010/admin/> |
| Readiness | <http://localhost:8010/api/health/ready/> |

`scripts/smoke.py` checks a running deployment from outside: every endpoint in
three languages, then an admin sign-in per role.

```sh
python scripts/smoke.py http://localhost:8010 \
  --token "$(docker compose exec -T web python manage.py demo_token)"
```

### Local

Needs [uv](https://docs.astral.sh/uv/). Without `DATABASE_URL` and `REDIS_URL`
it uses SQLite and an in-process cache, and Celery tasks run inline.

```sh
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py seed
uv run python manage.py runserver
```

`seed` fills the catalogue (in three languages), the demo subscriber
`994516643342` and the staff accounts. Running it again keeps existing rows, so
edits made in the admin survive. `--refresh` restores the seeded catalogue rows
and `--reset` recreates the demo subscriber.

## Signing in

The app sends `Authorization: Bearer <access-jwt>`; services can use
`Token <key>`. There is no login screen yet (`users/otp/*` answers `501`), so
for now:

- `manage.py demo_token` prints a 30-day token for the demo subscriber. Paste
  it into Swagger's **Authorize** dialog.
- `DEMO_AUTH=true` makes requests without an `Authorization` header act as the
  demo subscriber.

`DEMO_AUTH` is off by default and does not follow `DJANGO_DEBUG`. With it on,
anyone who can reach the server can use that account, so keep it for local work
and demos. `.env.example` enables it.

## Languages

Send `Accept-Language: az`, `ru` or `en`. Anything else falls back to `en`, and
the answer carries `Content-Language`.

Error messages, success messages, `501` notices and catalogue copy are
translated. Error `code`s, ids and prices never change.

- Strings in code live in `locale/{az,ru}/LC_MESSAGES/django.po`.
  `manage.py sync_locale` rewrites them from the code and compiles the `.mo`
  files without GNU gettext; with `--check` it fails on anything missing,
  untranslated or unused.
- Catalogue rows have one column per language
  ([django-modeltranslation](https://django-modeltranslation.readthedocs.io/)),
  shown as tabs in the admin.

## Admin

`/admin/`, built on [django-unfold](https://unfoldadmin.com/). `seed` creates
one account per role with the password from `SEED_STAFF_PASSWORD` (default
`aicell-demo`); a password changed later is not overwritten.

| Login | Role | Access |
|---|---|---|
| `superadmin` | Superadmin | everything |
| `content` | Content manager | catalogue and notifications, read and write |
| `support` | Support | subscribers and their activity, read only |
| `finance` | Finance | billing, read only |

Each role gets its own menu and dashboard. Transactions, top-ups and
idempotency keys are read-only for everyone, because money changes only through
the API.

## Endpoint status

| Tag | Meaning |
|---|---|
| `ready` | Implemented and tested |
| `:todo` | Routed at its final path; answers `501 not_implemented` with the notice text the app shows |
| `:dummy` | The assistant: works end to end with a keyword responder |

`/api/health/` and `/api/health/ready/` exist in addition to the documented
endpoints.

## How the code is laid out

```
config/            settings, celery, admin menu
api/common/        errors, auth, routing, schema, throttling, cache, health, admin bases
api/<domain>/      urls, views, services, catalogue, texts, models, translation, admin, tasks
api/seeding/       catalogue data, translations, demo subscriber, staff roles
locale/            az and ru catalogues
docs/api/          endpoint reference
scripts/smoke.py   check of a running deployment
```

Every domain has the same layers: `views.py` parses input and shapes JSON,
`services.py` holds the rules, `catalogue.py` reads catalogue rows (cached),
`texts.py` has fixed screen copy and `models.py` the state. Three things to
know:

- Balance changes go through one function, `billing.services.move`, which
  records the transaction in the same database transaction. Packs, SIM services
  and Steam all charge through it.
- A handler is described once with `@doc(...)`; `route()` builds the view, its
  permissions, throttling and Swagger entry from that.
- The catalogue lives in the database. The seed files only fill empty tables.

## Money

- A balance change runs in one transaction and locks the subscriber's wallet row
  first (`select_for_update`), so concurrent requests cannot overdraw it.
- Every money-moving `POST` needs `Idempotency-Key: <uuid>`. The key is stored
  with the charge; a repeat returns the first answer and charges nothing, even
  when both requests arrive together.
- "Already active" checks for services and auto-renewing packs run under the
  same lock.

## Tests

```sh
uv run pytest                              # SQLite; Postgres and Redis tests are skipped
uv run ruff check . && uv run ruff format --check .
```

To run everything, including the parallel-request tests, start the database
services and point the suite at them (use a Redis database of its own; tests
clear it):

```sh
docker compose up -d db redis
DATABASE_URL=postgres://aicell:<POSTGRES_PASSWORD>@127.0.0.1:54329/aicell \
REDIS_URL=redis://127.0.0.1:63799/15 \
uv run pytest
```

| File | Covers |
|---|---|
| `test_docs_conformance.py` | every row of `docs/api/*.md` exists and behaves as tagged |
| `test_isolation.py` | two subscribers: no read leaks, foreign ids are `404`, no token is `401` |
| `test_robustness.py` | malformed bodies, queries and content types never give a `500` |
| `test_concurrency.py` | Postgres only: parallel purchases and top-ups, one key sent twice at once |
| `test_languages.py` | every read in az/ru/en, nothing untranslated |
| `test_swagger.py` | schema validity, recorded examples against live answers |
| `test_admin.py` | every model's pages open, roles see their share, money is read-only |
| `test_catalogue.py` | admin edits reach the API; the cache is per language |
| `test_throttling.py`, `test_health.py`, `test_security.py` | limits, probes, deployment settings |

## Operations

**Health.** `GET /api/health/` only says the process is up. `GET
/api/health/ready/` checks the database, Redis and the Celery broker and
returns `503` if one fails. A part that is not configured (no Redis in a local
run) is reported as `not_configured` and does not fail the probe.

**Limits.** Counted in the cache; a `429` carries `Retry-After`. An empty value
turns a limit off.

| Setting | Default | Scope |
|---|---|---|
| `THROTTLE_OTP_IP`, `THROTTLE_OTP_PHONE` | `5/min` | `otp/*`, per address and per number |
| `THROTTLE_MONEY` | `30/min` | money-moving `POST`s, per subscriber |
| `THROTTLE_SUBSCRIBER` | `300/min` | everything else, per subscriber |

Behind a proxy, set DRF's `NUM_PROXIES` or the per-address limit will see only
the proxy.

**Cache.** Catalogue answers are cached per language and the whole catalogue
cache is dropped when any catalogue row is saved or deleted. Subscriber data is
never cached.

**Scheduled work** (Celery beat): expired pack activations are switched off every
minute; idempotency keys older than `IDEMPOTENCY_KEY_DAYS` are purged hourly.

**Swagger examples.** Response examples come from `api/common/examples.json`,
recorded from real answers by `manage.py record_examples` (it runs in a
transaction that is rolled back). Run it after changing a response; a test
fails if the file is stale.

## Configuration

Read from the environment, and from `.env` when present.

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_DEBUG` | `false` | |
| `DJANGO_SECRET_KEY` | none | required unless debug is on |
| `DJANGO_ALLOWED_HOSTS` | none (`localhost,127.0.0.1` in debug) | comma-separated |
| `CORS_ALLOWED_ORIGINS` | none | all origins are allowed in debug |
| `CSRF_TRUSTED_ORIGINS` | none | origins the admin is served from |
| `SECURE_SSL_REDIRECT`, `SECURE_COOKIES` | `true` | `false` only for plain-HTTP local runs |
| `SECURE_HSTS_SECONDS` | `31536000` | |
| `DATABASE_URL` | SQLite file | `postgres://…` in Docker |
| `REDIS_URL` | none | cache, limits and the Celery broker |
| `DEMO_AUTH` | `false` | see [Signing in](#signing-in) |
| `GOOGLE_PAY_SIMULATED` | follows `DJANGO_DEBUG` | accepts `payment_token: "simulated"` |
| `SEED_STAFF_PASSWORD` | `aicell-demo` | change it on anything public |
| `THROTTLE_*` | see Limits | |
| `CATALOGUE_CACHE_SECONDS` | `300` | |
| `ASSISTANT_RESPONDER` | `api.assistant.responder.respond` | dotted path to a callable |

With debug off, cookies are secure-only, HSTS is on, HTTP is redirected to
HTTPS (except the health probes) and `X-Forwarded-Proto` is trusted.
`manage.py check --deploy` is clean in that configuration.

`docker-compose.yml` serves plain HTTP on localhost, so it sets
`SECURE_SSL_REDIRECT=false` and `SECURE_COOKIES=false`. `check --deploy` then
reports exactly three warnings (`W008`, `W012`, `W016`). Remove both overrides
behind TLS.

## Known limitations

- The assistant calls no model; it matches keywords and answers in English.
  `ASSISTANT_RESPONDER` points at the callable, so a model-backed one with the
  same signature can replace it.
- Some catalogue content is placeholder: where the docs abbreviate a list with
  `…`, the missing entries were written in the documented shape and are
  ordinary rows now.
- Translations were written for this project, not taken from approved copy.
- Image fields are absolute URLs under `/media/content/`; the image files are
  not in the repository.
- The admin's built-in labels follow the browser language, not `Accept-Language`.

## Where the server departs from the docs

The docs contradict themselves in three places; the server picks one side:

| Docs | Server |
|---|---|
| `top-ups/` has ids like `"h01"`, `top-up/card/` returns `"id": 16` | integer ids everywhere |
| `my/usage/` shows `data_total_gb: "20"`, `my/` shows a 16 GB total | `"16"`, from the same row as `my/` |
| `renewal_label` says `00:00`, the next payment date says `08:00+04:00` | the label follows the payment date: `08:00` |

Where the docs leave a shape open: `stories/` and `internet/top/` return
`{ "results": [...] }`, `POST stories/<key>/viewed/` returns
`{ "key", "viewed": true }`, and an assistant turn in JSON returns
`{ "user_message_id", "message", "action" }`.

## Stack

Django 5.2, Django REST framework, SimpleJWT, drf-spectacular, django-unfold,
django-modeltranslation, Celery, Redis, PostgreSQL, gunicorn, WhiteNoise, pytest.
All data is synthetic.
