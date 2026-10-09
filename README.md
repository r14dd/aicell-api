# aicell-api

<p align="center">
  <a href="https://github.com/r14dd/aicell-api/actions/workflows/ci.yml"><img src="https://github.com/r14dd/aicell-api/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.13-blue.svg?logo=python&logoColor=white" alt="Python 3.13">
  <img src="https://img.shields.io/badge/django-5.2-0C4B33.svg?logo=django" alt="Django 5.2">
  <img src="https://img.shields.io/badge/DRF-3.18-A30000.svg" alt="Django REST framework 3.18">
  <img src="https://img.shields.io/badge/tests-1506%20passing-brightgreen.svg" alt="1470 tests">
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
   spoken sentence in az or en; `POST /api/laya/plan/` turns what the user
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
| Endpoints | 82 working, documented in [docs/api](docs/api/overview.md) |
| Languages | Azerbaijani, Russian, English, from `Accept-Language` |
| Tests | 1506, every documented endpoint checked against the docs in three languages |
| Money | One code path for every balance change, row-locked, idempotent; parallel requests cannot overdraw |
| Admin | django-unfold, four roles, a usage statistics page with trends, segments and offer results |
| Run | `docker compose up -d --build` (API, Celery worker and beat, Redis, SQLite) |

The mobile client lives in a separate repository;
[docs/mobile-integration.md](docs/mobile-integration.md) is the guide for wiring
it (in Azerbaijani).

**Not real yet.** Usage comes from seed data (there is no network feed), top-ups
do not reach a payment provider, and sign-in takes a fixed test code until an
SMS provider is wired in. See
[Known limitations](docs/architecture.md#known-limitations).

## The support assistant

`api/assistant/` is the in-app support chat ([docs/api/assistant.md](docs/api/assistant.md)).
With `GEMINI_API_KEY` set, Gemini routes each message, answers from the
subscriber's own data or a Milvus knowledge base, and streams the reply (SSE).
`POST conversations/<id>/voice/` takes a recording (wav, mp3, m4a, ogg, webm)
and returns the transcript, the answer and the answer as speech. Without a key
a keyword responder answers.

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

Error messages, success messages and catalogue copy are
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

## Development

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Test layout, Redis and PostgreSQL runs: [docs/architecture.md](docs/architecture.md#tests).

## Documentation

- [docs/api](docs/api/overview.md): endpoint reference
- [docs/architecture.md](docs/architecture.md): code layout, usage and insight engines, money, operations, configuration, known limitations
- [docs/mobile-integration.md](docs/mobile-integration.md): wiring the mobile client (Azerbaijani)

## Stack

Django 5.2, Django REST framework, SimpleJWT, drf-spectacular, django-unfold,
django-modeltranslation, Celery, Redis, SQLite, Gemini and Claude (Laya, the
support assistant, speech), Milvus, gunicorn, WhiteNoise, pytest.
All data is synthetic.

## License

[MIT](LICENSE).
