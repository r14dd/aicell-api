# api/common

Shared building blocks. A Django app (label `common`) only to hold management commands; it has no tables.

| File | Holds |
|---|---|
| `routing.py`, `docs.py` | `route(tag, get=..., post=...)`, `Todo`, `RouteView`; `@doc(summary, body=, query=, example=, path=, errors=, status=, streams=)` |
| `schema.py` | turns `@doc` into OpenAPI; `ErrorSerializer`; `examples()` reads `examples.json` |
| `exceptions.py` | `ApiError` family, `TokenExpired`, `exception_handler`, `not_found_view` |
| `http.py` | `validated`, `validated_query`, `paginate`, `date_range`, `AmountField`, `MsisdnField`, `PageQuery`, `DateRangeQuery`, `media`, `with_images` |
| `formatting.py` | `money` ("16.21"), `iso` (UTC `Z`), `iso_local` (+04:00) |
| `auth.py`, `middleware.py` | `BearerAuthentication`, `DemoAuthentication`; `ApiLanguageMiddleware` (skips `/api/health/`) |
| `throttling.py` | `SUBSCRIBER`, `MONEY`, `OTP` throttle sets; rates from `settings.THROTTLE_RATES` |
| `cache.py` | `@cached(name)` for catalogue readers, `invalidate()` |
| `models.py` | abstract `CatalogueItem` (`order`, `is_active`), `ActiveQuerySet.active()` |
| `health.py` | `LiveView`, `ReadyView` (plain DRF views, not `route()`) |
| `admin.py`, `dashboard.py` | `BaseAdmin`, `ReadOnlyAdmin`, `CatalogueAdmin`, `ReadOnlyInline`, `language_tabs`, `manat`; admin index figures by permission |
| `management/commands/` | `seed`, `sync_locale`, `record_examples`, `demo_token` |

## Not obvious from the code
- `route()` chooses throttles from the handler: `throttle="otp"` → `OTP`; handler wrapped in `@idempotent` → `MONEY`; else `SUBSCRIBER`.
- `@doc` is required on every ready handler (`handler.doc` is read at import). Path parameters need a sample in `path=`; `record_examples` builds URLs from them.
- `schema.example_key` is `"<METHOD> <domain>.<handler __name__>"`; a renamed handler needs `record_examples`.
- `@cached` readers take no arguments, must return plain JSON data (no lazy strings, no request-dependent URLs: image names are absolutised later by `with_images`). Key includes language and a version; any `CatalogueItem` save/delete bumps the version (signal in `cache.py`).
- `exceptions.py` imports `set_rollback` inside the handler on purpose (circular import with DRF auth loading). `TokenExpired` is raised in `auth.py` by exception type, so `token_expired` does not depend on the language.
- Unknown `/api/...` paths hit the catch-all at the end of `api/urls.py` → JSON 404.
- Admin labels are plain English (no `_()`); `sync_locale` scans all of `api/`, so a `_()` there would need az/ru entries.

Tests: `tests/test_conventions.py`, `tests/test_swagger.py`, `tests/test_throttling.py`, `tests/test_health.py`, `tests/test_security.py`, `tests/test_architecture.py`.
