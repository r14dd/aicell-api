# Architecture and operations

The details behind the [README](../README.md).

## Endpoint status

| Tag | Meaning |
|---|---|
| `ready` | Implemented and tested |
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
([docs/api/usage.md](api/usage.md)).

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
([docs/api/insights.md](api/insights.md)): the internet will not last
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
| `test_sign_in.py` | OTP sign-in and per-subscriber tokens |
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
| `DEMO_AUTH` | `false` | see [Signing in](../README.md#signing-in) |
| `GOOGLE_PAY_SIMULATED` | follows `DJANGO_DEBUG` | accepts `payment_token: "simulated"` |
| `SEED_STAFF_PASSWORD` | `aicell-demo` | change it on anything public |
| `THROTTLE_*` | see Limits | |
| `CATALOGUE_CACHE_SECONDS` | `300` | |
| `DEMO_ADMIN_LOGIN` | `false` | one passwordless button per seeded staff account on the admin login page |
| `LAYA_PLAN_MODEL`, `LAYA_NARRATE_MODEL` | Sonnet / Haiku | the Claude brain's models |
| `WEB_PORT`, `REDIS_PORT` | `8010`, `63799` | published ports in Docker |
| `INSIGHTS_QUIET_HOURS` | `true` | `false` delivers insights at night too (23:00 to 08:00 Asia/Baku) |
| `GEMINI_API_KEY` | none | turns on the Gemini assistant, voice and Laya brain |
| `GEMINI_MODEL`, `GEMINI_STT_MODEL`, `GEMINI_TTS_MODEL`, `GEMINI_EMBED_MODEL`, `GEMINI_VOICE` | see `config/settings.py` | chat, speech to text, text to speech, embeddings, voice name |
| `ANTHROPIC_API_KEY` | none | Laya's brain when there is no Gemini key |
| `MILVUS_URI` | `data/knowledge.db` | knowledge and memory store: a file (Milvus Lite) or `http://milvus:19530` |
| `ASSISTANT_RESPONDER` | `api.assistant.agent.respond` with a Gemini key, else `api.assistant.responder.respond` | dotted path to a callable |

With debug off, cookies are secure-only, HSTS is on, HTTP is redirected to
HTTPS (except the health probes) and `X-Forwarded-Proto` is trusted.
`manage.py check --deploy` is clean in that configuration.

`docker-compose.yml` serves plain HTTP on localhost, so it sets
`SECURE_SSL_REDIRECT=false` and `SECURE_COOKIES=false`. `check --deploy` then
reports exactly three warnings (`W008`, `W012`, `W016`). Remove both overrides
behind TLS.

## Known limitations

A pre-deploy check of the demo configuration is in [deploy-readiness.md](deploy-readiness.md) (in Azerbaijani).

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
- Without `GEMINI_API_KEY` the support assistant falls back to keyword rules and
  answers in English. `ASSISTANT_RESPONDER` points at the callable.
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
