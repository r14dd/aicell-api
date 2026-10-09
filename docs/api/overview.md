# API Reference — Conventions

All endpoints are mounted under `/api/` (`config/urls.py`) and grouped by
domain (`api/urls.py`):

```python
(path("users/", include("api.users.urls")),)
(path("billing/", include("api.billing.urls")),)
(path("tariffs/", include("api.tariffs.urls")),)
(path("packs/", include("api.packs.urls")),)
(path("kredit/", include("api.kredit.urls")),)
(path("sim/", include("api.sim.urls")),)
(path("content/", include("api.content.urls")),)
(path("referral/", include("api.referral.urls")),)
(path("assistant/", include("api.assistant.urls")),)
(path("usage/", include("api.usage.urls")),)
```

Schema: `GET /api/schema/`, Swagger UI: `GET /api/swagger/`.

## Headers

| Header | Value |
|---|---|
| `Authorization` | `Bearer <access-jwt>` (mobile) or `Token <key>` (services) |
| `Accept-Language` | `en`, `az`, `ru` — copy fields are returned in that language when a translation exists, else `en` |
| `X-App-Version` | `5.1.0 (13557)` |
| `X-Platform` | `ios`, `android`, `web` |
| `Idempotency-Key` | UUID, required on every `POST` that moves money |

## Shapes

- Money is a decimal **string** with two decimals: `"16.21"`. Currency is
  always `AZN` and omitted unless stated.
- Timestamps are ISO 8601 UTC: `"2026-10-02T12:39:00Z"`. The client
  formats ("02 October", "16:39").
- MSISDN in and out is `994XXXXXXXXX`; the client formats `051 664 33 42`.
- Lists return `{ "results": [...] }`. Long lists (transactions, top-ups,
  notifications, messages) add cursor pagination:
  `{ "results": [...], "next": "<cursor>|null" }` with `?cursor=` and
  `?limit=` (default 50).
- Images are absolute URLs.
- Deep links are Expo Router paths (`"/kredit/tamamla"`) or `null`.

## Errors

```json
{ "code": "insufficient_balance", "detail": "Not enough balance for this pack" }
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `validation_error` | serializer errors; `errors` field lists them |
| 401 | `not_authenticated` / `token_expired` | |
| 402 | `insufficient_balance` | wallet charge fails |
| 403 | `forbidden` | not the owner / not premium |
| 404 | `not_found` | |
| 409 | `already_active` | pack / service already active |
| 409 | `offer_closed` | personal offer already accepted, declined or expired |
| 409 | `insight_closed` | insight already accepted or dismissed |
| 429 | `rate_limited` | OTP sends, assistant messages |
| 501 | `not_implemented` | every `:todo` endpoint returns this with `detail` = the mobile notice text, so the client can keep showing the same toast |

## Status tags

Every row in the domain pages carries `ready`, `:todo` or `:dummy` (see
the README). `:todo` endpoints **exist** and
return `501 not_implemented` so the mobile client can be wired to the
final paths now.

## Domain pages

- [users](users.md)
- [billing](billing.md)
- [tariffs](tariffs.md)
- [packs](packs.md)
- [kredit](kredit.md)
- [sim](sim.md)
- [content](content.md)
- [referral](referral.md)
- [assistant](assistant.md)
- [usage](usage.md)
