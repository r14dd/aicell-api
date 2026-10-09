# aicell-api

<p align="center">
  <a href="https://github.com/r14dd/aicell-api/actions/workflows/ci.yml"><img src="https://github.com/r14dd/aicell-api/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.13-blue.svg?logo=python&logoColor=white" alt="Python 3.13">
  <img src="https://img.shields.io/badge/django-5.2-0C4B33.svg?logo=django" alt="Django 5.2">
  <img src="https://img.shields.io/badge/DRF-3.18-A30000.svg" alt="Django REST framework 3.18">
  <img src="https://img.shields.io/badge/tests-1470%20passing-brightgreen.svg" alt="1470 tests">
  <img src="https://img.shields.io/badge/languages-az%20%7C%20ru%20%7C%20en-informational.svg" alt="az, ru, en">
  <img src="https://img.shields.io/badge/docker-compose-2496ED.svg?logo=docker&logoColor=white" alt="Docker Compose">
</p>

`aicell-api` is the backend of a mobile operator's self-service app. Besides the
usual balance, tariffs, packs and SIM settings, it reads how each subscriber
actually uses the number and tells them, in manats, where they are overpaying
and what to switch to. An assistant called Laya says it in their language and
does it for them in one tap.

> Every number a subscriber sees is computed by the backend from their own
> usage and the live catalogue. The AI only picks the intent and words the
> sentence; an answer that contains a number the backend did not give it is
> thrown away.

## The problem

A prepaid subscriber pays for a tariff and then, when the internet runs out,
for packs on top. Nobody tells them that:

- the tariff plus the packs they keep buying cost more than the next tariff
  up, which already includes that much internet (32.98 ₼ against 30.00 ₼ for
  one of the seeded subscribers);
- most of their traffic is one app that has a much cheaper pack of its own;
- half of the included internet is left over at the end of every month;
- their internet will run out four days before the renewal at today's rate;
- the renewal is tomorrow and the balance is 2.89 ₼ short.

The operator has all of this data and shows none of it. The subscriber finds
out from an empty balance or a per-megabyte charge (0.05 ₼/MB, about 51 ₼ for
a gigabyte).

**For whom.** Subscribers of a mobile operator who manage their line in the
app (the screens are in [docs/api](docs/api/overview.md)), and the operator's
staff, who see the same figures across all subscribers in the admin.

## What it does about it

| Problem | What the backend finds | What the subscriber gets |
|---|---|---|
| Packs bought on top of the tariff, again and again | `repeat_packs`: two or more add-on packs in one period | The cheapest catalogue plan that covers the monthly usage, with the monthly saving |
| Internet will not last until the renewal | `forecast_gap`: 7-day burn rate × days left > what is left | The smallest pack that closes the gap, and a cheaper fallback |
| Charged per megabyte right now | `overage`: tariff empty, out-of-package traffic today | A day pack now, a pack for the days left, with what it saves against 0.05 ₼/MB |
| Paying for internet nobody uses | `underused`: half the tariff left over three periods running | IsteSen with fewer gigabytes, or a cheaper plan, with the yearly saving |
| A big pack gone in three days, mostly video | `video_heavy` | The YouTube or TikTok pack sized to that use, priced against the same gigabytes in the general pack |
| Most traffic is Instagram or TikTok | `social_heavy` | IsteSen sliders fitted to the usage ("IsteSen+"), or the app's own pack |
| Renewal tomorrow, balance short | `renewal_shortfall` | A top-up of the exact shortfall, rounded up to a manat |
| Roaming without a roaming pack | `roaming` | The roaming packs with the cheapest gigabyte |

On the seeded data: the heavy YouTube user pays 32.98 ₼ in 30 days and is shown
a 20 GB pack that would have cost 5.98 ₼ less; the frequent traveller is shown a
roaming pack that saves 15.00 ₼; the subscriber whose plan already fits is told
so, with no offer at all.

## How it works

```
usage per day and app ─┐
pack purchases         ├─► figures ──► detectors ──► insight { evidence, offers[], task }
tariff, wallet         ┘   (burn rate,   (plain rules,     │
live catalogue ──────────►  shares,       thresholds as    ├─► GET /api/insights/          the app's cards
                            monthly cost)  constants)      ├─► GET /api/insights/advisor/  "IsteSen+" vs plans
                                                           └─► POST /api/laya/narrate/     one spoken sentence
```

1. **Figures.** From daily and per-app usage, purchases, the tariff and the
   wallet: burn rate, days left, the gap, video and social shares, the monthly
   cost (`api/insights/metrics.py`).
2. **Detectors.** Eight plain functions, each returns the facts it found and
   the priced answers, or nothing (`api/insights/detectors.py`).
3. **Offers from the live catalogue.** Packs and plans are read from the
   tables and ranked by price and price per gigabyte; a pack added in the
   admin is chosen by the same rules. No product is invented.
4. **Delivery decided on the server.** Urgent insights always, one new
   informational insight per 48 hours, nothing between 23:00 and 08:00 Baku
   time, a dismissed kind silent for 14 days.
5. **One tap to act.** Each offer carries a `task` the app runs through the
   endpoint that sells it: `buyPack`, `activatePack`, `changeTariff`,
   `applyRedesign`, `topUp`. Money moves only there, under an idempotency key.
6. **Laya words it.** `POST /api/laya/narrate/` turns one insight into one
   spoken sentence in az, ru or en; `POST /api/laya/plan/` turns what the user
   said ("hə", "niyə?", "balansım") into a task. Claude is forced to answer
   through a single tool call, and any number in the answer that is not in the
   request is rejected. Without an API key Laya falls back to keyword rules.

## What an answer means

The backend can show that a cheaper option **existed for the last 30 days of
usage**; it cannot promise next month looks the same. Every saving is the
difference between what was actually paid and what the candidate would have
cost for the same usage at catalogue prices. When nothing in the catalogue is
cheaper the answer is "your plan fits", and when a change saves less than
1 ₼ a month the advisor recommends staying.

## At a glance

| | |
|---|---|
| Endpoints | 127 documented in [docs/api](docs/api/overview.md): 82 working, 45 routed and answering `501` with the app's notice text (sign-in among them) |
| Languages | Azerbaijani, Russian, English, from `Accept-Language` |
| Tests | 1470, every documented endpoint checked against the docs in three languages |
| Money | One code path for every balance change, row-locked, idempotent; parallel requests cannot overdraw |
| Admin | django-unfold, four roles, a usage statistics page with trends, segments and offer results |
| Run | `docker compose up -d --build` (API, Celery worker and beat, Redis, SQLite) |

The mobile client lives in a separate repository;
[docs/mobile-integration.md](docs/mobile-integration.md) is the guide for wiring
it (in Azerbaijani).

**Not real yet.** Usage comes from seed data (there is no network feed), top-ups
do not reach a payment provider, sign-in (OTP) is not built, and the support
inbox assistant needs a Gemini key (`GEMINI_API_KEY`); without one it answers by
keywords in English. See
[Known limitations](#known-limitations).

## Run it

### Docker

```sh
cp .env.example .env     # set DJANGO_SECRET_KEY
docker compose up --build
```

This starts the API (gunicorn), Redis, a Celery worker and Celery beat. The
database is one SQLite file on a volume the three app containers share. The
`web` container migrates, collects static files and seeds before it serves.

The stack no longer runs PostgreSQL, and a database from an earlier `docker compose up`
(the old `pgdata` volume) is not read: the first start creates an empty SQLite file. To
keep using PostgreSQL, set `DATABASE_URL=postgres://user:password@host:5432/name` in `.env`.

`GEMINI_API_KEY` in `.env` reaches the containers. The assistant's knowledge store is a
file under the data volume by default (`MILVUS_URI`). To use a Milvus server instead, set
`MILVUS_URI=http://milvus:19530` in `.env` and start the stack with
`docker compose --profile milvus up`; the `milvus` service is not started otherwise.

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

Needs [uv](https://docs.astral.sh/uv/). The database is `db.sqlite3`; without
`REDIS_URL` the cache is in-process and Celery tasks run inline.

```sh
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py seed
uv run python manage.py runserver
```

`seed` fills the catalogue (in three languages), five subscribers with a 30-day
usage story each and the staff accounts. Running it again keeps existing rows,
so edits made in the admin survive. `--refresh` restores the seeded catalogue
rows and `--reset` recreates the five subscribers. `manage.py demo_token
<msisdn>` prints a token for any of them.

| Number | Story |
|---|---|
| `994516643342` | Demo subscriber on IsteSen: moderate use, more than half of it Instagram |
| `994501000001` | Heavy YouTube user on DigiMax 5GB who keeps buying add-on packs |
| `994501000002` | Calls only: has never used mobile data |
| `994501000003` | Frequent roamer paying with small roaming packs |
| `994501000004` | Balanced use: the current plan fits |

`seed --crowd 300` also keeps 300 synthetic subscribers (`994559000001`…) with
90 days of usage, top-ups and pack purchases, so the usage statistics have
something to show. The same number always gives the same crowd; `--crowd 0`
removes it.

## Signing in

The app sends `Authorization: Bearer <access-jwt>`; services can use
`Token <key>`. A subscriber signs in with the number alone: `users/otp/send/`
starts a sign-in and `users/otp/verify/` accepts `000000` (`OTP_TEST_CODE`)
for every number until an SMS provider is wired in. Each token sees only its
own subscriber's data. Staff accounts cannot sign in this way.

- `manage.py demo_token <msisdn>` prints a 30-day token without the round trip.
  Paste it into Swagger's **Authorize** dialog.
- `DEMO_AUTH=true` makes requests without an `Authorization` header act as the
  demo subscriber.

`DEMO_AUTH` is off by default and does not follow `DJANGO_DEBUG`. With it on,
anyone who can reach the server can use that account, so keep it for local work
and demos. `.env.example` leaves it off; set `DEMO_AUTH=true` in `.env` to use it.

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

**Usage statistics** (`/admin/usage/dailyusage/statistics/`, menu "Usage and
offers") shows how subscribers use the network: headline figures with the
change against the previous period, data and call minutes per day, data by
category and app, segments, personal-offer results and the top subscribers.
The period, segment and line type are in the query string, so a filtered view
is a link. It is open to accounts that may view usage data (`superadmin` and
`support`), who also get a "Usage" tab on a subscriber's page. Every figure is
one aggregation in the database (`api/usage/statistics.py`); segments and
savings come from rows an hourly task recomputes (`api/usage/insights.py`).

## Endpoint status

| Tag | Meaning |
|---|---|
| `ready` | Implemented and tested |
| `:todo` | Routed at its final path; answers `501 not_implemented` with the notice text the app shows |
| `:dummy` | The assistant: works end to end; Gemini when `GEMINI_API_KEY` is set, a keyword responder otherwise |

`/api/health/` and `/api/health/ready/` exist in addition to the documented
endpoints.

## How the code is laid out

```
config/            settings, celery, admin menu
api/common/        errors, auth, routing, schema, throttling, cache, health, admin bases
api/<domain>/      urls, views, services, catalogue, texts, models, translation, admin, tasks
api/usage/         usage per day and app, recommendations, personal offers, statistics
api/insights/      detectors, metrics, offers, advisor
api/laya/          plan and narrate; Gemini or Claude brain, keyword fallback, number guard
api/assistant/     inbox assistant: text, SSE, voice; Gemini agent, knowledge, per-subscriber memory
api/seeding/       catalogue data, translations, seeded subscribers, staff roles
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

## Usage and recommendations

`api/usage/` keeps usage per day and per app, builds a 30-day profile from it
and turns the profile into ranked recommendations and personal offers
([docs/api/usage.md](docs/api/usage.md)).

- Every number is arithmetic. For each candidate (another plan, the current
  plan plus one pack, other roaming packs, IsteSen slider values) the last 30
  days are re-priced with the catalogue's included amounts and out-of-package
  prices and compared with what was actually paid. No model is called. When
  nothing is cheaper the answer says the plan fits.
- Apps and categories live in one mapping (`api/usage/taxonomy.py`), with what
  can be sold for each category. A category with nothing to sell is reported
  as an insight only.
- Personal offers come from rules staff define in the admin by segment; a
  scheduled task applies them and announces each with a notification.
- `api.usage.assistant.context(subscriber)` returns the profile, the top
  recommendations and the open offer as one small dict for a model-backed
  responder. The keyword responder already answers "which tariff suits me"
  from the same numbers.

## Insights

`api/insights/` turns the same figures into things worth telling a subscriber
([docs/api/insights.md](docs/api/insights.md)): the internet will not last
until the renewal, the balance does not cover it, packs keep being bought on
top of the tariff, half of the tariff is left over every month.

- Detectors are plain functions of the subscriber's figures and a snapshot of
  the catalogue (`detectors.py`). Each returns the facts it found and the
  priced answers, or nothing. Thresholds are named constants.
- Offers are picked from the catalogue tables by price and price per
  gigabyte (`catalogue.py`), so a pack added in the admin is chosen by the
  same rules. Nothing is hard-coded and no product is invented.
- The backend writes no sentences. An insight is `evidence` plus `offers`;
  the assistant or the app words it. Every price and saving is already
  computed, so a model that words it has nothing to calculate.
- Delivery is decided on the server: urgent insights always, one new
  informational one per 48 hours, none at night, a dismissed kind silent for
  14 days.
- `GET insights/advisor/` compares what a month costs now with IsteSen
  redesigned to the usage ("IsteSen+") and with the cheapest plan that covers
  it.

## Tariffs

`subscribe/`, `change/` and `my/renew/` charge the wallet and start a full
period: remaining amounts go back to the total and the payment dates move on.
`my/redesign/` stores the IsteSen slider values without charging; the next
renewal applies them. `my/usage/` reports the tariff plus active internet
packs, as the aggregation sheet describes.

## Money

- A balance change runs in one transaction that holds a lock before it reads
  the balance, so concurrent requests cannot overdraw it. On SQLite the
  transaction takes the database's write lock as it begins
  (`transaction_mode: IMMEDIATE`); on PostgreSQL the wallet row is locked
  (`select_for_update`).
- Every money-moving `POST` needs `Idempotency-Key: <uuid>`. The key is stored
  with the charge; a repeat returns the first answer and charges nothing, even
  when both requests arrive together.
- "Already active" checks for services and auto-renewing packs run under the
  same lock.

## Tests

```sh
uv run pytest                              # SQLite; the PostgreSQL and Redis tests are skipped
uv run ruff check . && uv run ruff format --check .
```

The Redis tests run when `REDIS_URL` is set (use a database of its own; tests
clear it). The parallel-request tests need row locks, so they run only against
a PostgreSQL server given in `DATABASE_URL`:

```sh
docker compose up -d redis
REDIS_URL=redis://127.0.0.1:63799/15 uv run pytest
DATABASE_URL=postgres://user:password@127.0.0.1:5432/name uv run pytest tests/test_concurrency.py
```

| File | Covers |
|---|---|
| `test_docs_conformance.py` | every row of `docs/api/*.md` exists and behaves as tagged |
| `test_isolation.py` | two subscribers: no read leaks, foreign ids are `404`, no token is `401` |
| `test_robustness.py` | malformed bodies, queries and content types never give a `500` |
| `test_concurrency.py` | PostgreSQL only: parallel purchases and top-ups, one key sent twice at once |
| `test_languages.py` | every read in az/ru/en, nothing untranslated |
| `test_swagger.py` | schema validity, recorded examples against live answers |
| `test_admin.py` | every model's pages open, roles see their share, money is read-only |
| `test_catalogue.py` | admin edits reach the API; the cache is per language |
| `test_usage.py` | profile and top recommendation of each seeded persona; cost arithmetic by hand; offers charge once |
| `test_statistics.py` | every statistics figure against a hand-built data set; period boundaries; filters; 403 without the permission; a query-count ceiling |
| `test_insights.py` | the figures; each detector firing and not firing on hand-built data; one open insight per kind; the delivery policy; the advisor's arithmetic |
| `test_tariff_actions.py` | subscribe, change, renew and redesign; nothing changes without the money |
| `test_laya.py` | plan and narrate, the number guard, both brains |
| `test_demo_login.py` | the passwordless admin login, off by default |
| `test_billing.py`, `test_products.py`, `test_sim.py`, `test_content.py`, `test_upgrade.py` | the money, packs, SIM and content endpoints |
| `test_throttling.py`, `test_health.py`, `test_security.py` | limits, probes, deployment settings, compose passes every setting |

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
minute; personal offers are created and expired every 15 minutes and subscriber
insights recomputed hourly; the insight detectors run for everyone at 03:00;
idempotency keys older than `IDEMPOTENCY_KEY_DAYS` are purged hourly.

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
| `DATABASE_URL` | SQLite file | a volume path in Docker; `postgres://…` also works |
| `REDIS_URL` | none | cache, limits and the Celery broker |
| `DEMO_AUTH` | `false` | see [Signing in](#signing-in) |
| `GOOGLE_PAY_SIMULATED` | follows `DJANGO_DEBUG` | accepts `payment_token: "simulated"` |
| `SEED_STAFF_PASSWORD` | `aicell-demo` | change it on anything public |
| `THROTTLE_*` | see Limits | |
| `CATALOGUE_CACHE_SECONDS` | `300` | |
| `DEMO_ADMIN_LOGIN` | `false` | one passwordless button per seeded staff account on the admin login page |
| `GEMINI_API_KEY` | none | the assistant and Laya use Gemini when set |
| `GEMINI_MODEL`, `GEMINI_STT_MODEL`, `GEMINI_TTS_MODEL`, `GEMINI_EMBED_MODEL`, `GEMINI_VOICE` | see `config/settings.py` | text, speech-to-text, text-to-speech, embeddings, voice name |
| `ANTHROPIC_API_KEY` | none | Laya uses Claude when set and no Gemini key is |
| `LAYA_PLAN_MODEL`, `LAYA_NARRATE_MODEL` | Sonnet / Haiku | the Claude brain's models |
| `MILVUS_URI` | `data/knowledge.db` | knowledge and memory store: a file (Milvus Lite) or `http://milvus:19530` |
| `WEB_PORT`, `REDIS_PORT` | `8010`, `63799` | published ports in Docker |
| `INSIGHTS_QUIET_HOURS` | `true` | `false` delivers insights at night too (23:00 to 08:00 Asia/Baku) |
| `ASSISTANT_RESPONDER` | `api.assistant.responder.respond` | dotted path to a callable |

With debug off, cookies are secure-only, HSTS is on, HTTP is redirected to
HTTPS (except the health probes) and `X-Forwarded-Proto` is trusted.
`manage.py check --deploy` is clean in that configuration.

`docker-compose.yml` serves plain HTTP on localhost, so it sets
`SECURE_SSL_REDIRECT=false` and `SECURE_COOKIES=false`. `check --deploy` then
reports exactly three warnings (`W008`, `W012`, `W016`). Remove both overrides
behind TLS.

## Known limitations

A pre-deploy check of the demo configuration is in [docs/deploy-readiness.md](docs/deploy-readiness.md) (in Azerbaijani).

- Insights rest on what is recorded per day. Signals that need hourly traffic
  (Teams during work hours, a gigabyte within an hour) are not built. How much
  of a pack is used is not tracked either: "a pack was used up in three days"
  is read from the home data of the days after it was bought.
- Insight detectors run when the app asks and once a night. No purchase or
  top-up pushes an insight on its own; there is no push channel yet.
- Usage is synthetic. No network feed exists; the usage histories are written
  by the seed, and nothing decrements a tariff's remaining amounts.
  Recommendations are real arithmetic over that data, so they are only as
  realistic as the seeded stories and the placeholder prices.
- The cost model is simple: one change per candidate, the window treated as one
  billing month, the tariff fee taken from the tariff record, roaming minutes
  not priced.
- Without `GEMINI_API_KEY` the assistant matches keywords and answers in
  English. `ASSISTANT_RESPONDER` points at the callable, so another responder
  with the same signature can replace it.
- Some catalogue content is placeholder: where the docs abbreviate a list with
  `…`, the missing entries were written in the documented shape and are
  ordinary rows now.
- Translations were written for this project, not taken from approved copy.
- Image fields are absolute URLs under `/media/content/`; the image files are
  not in the repository.
- The admin's built-in labels follow the browser language, not `Accept-Language`.

## Where the server departs from the docs

The docs contradict themselves in two places and one example was read differently; the server picks one side:

| Docs | Server |
|---|---|
| `top-ups/` has ids like `"h01"`, `top-up/card/` returns `"id": 16` | integer ids everywhere |
| `my/usage/` shows `data_total_gb: "20"`, `my/` shows a 16 GB total | the tariff plus active internet packs, as the aggregation sheet says: `"16"` for the seeded subscriber, `"21"` with a 5 GB pack |
| `renewal_label` says `00:00`, the next payment date says `08:00+04:00` | the label follows the payment date: `08:00` |

Where the docs leave a shape open: `stories/` and `internet/top/` return
`{ "results": [...] }`, `POST stories/<key>/viewed/` returns
`{ "key", "viewed": true }`, and an assistant turn in JSON returns
`{ "user_message_id", "message", "action" }`.

## Stack

Django 5.2, Django REST framework, SimpleJWT, drf-spectacular, django-unfold,
django-modeltranslation, Celery, Redis, SQLite, Gemini and Claude (Laya), Milvus,
gunicorn, WhiteNoise, pytest.
All data is synthetic.
