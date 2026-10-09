# api/users

The subscriber account and the (not yet built) sign-in. Docs: `docs/api/users.md`.

## Model
- `Subscriber` — `AUTH_USER_MODEL`. `USERNAME_FIELD` is `msisdn` (`994XXXXXXXXX`); `display_msisdn` is computed (`051 664 33 42`).

## Endpoints (`/api/users/`)
| Method | Path | Status |
|---|---|---|
| GET | `me/` | ready |
| PATCH | `me/` | :todo |
| POST | `otp/send/`, `otp/verify/`, `token/refresh/` | :todo, public |
| POST | `logout/`, `devices/` | :todo |
| GET, PATCH | `me/app-settings/` | :todo |

## Not obvious from the code
- Admin staff are `Subscriber` rows too, with word logins (`superadmin`, `content`, `support`, `finance`) created by `api/seeding/staff.py`. Count real subscribers with `is_staff=False`.
- Every other domain hangs off `Subscriber` by FK/OneToOne with cascade; deleting one removes all its data (used by `seed --reset`).
- `me/` returns `app_version` as an echo of the `X-App-Version` header (`null` without it).
- `otp/*` and `token/refresh/` are `route(..., public=True)`: no authentication runs. `otp/*` use `throttle="otp"` (per IP and per `msisdn` in the body).
- JWTs are minted with `rest_framework_simplejwt.tokens.AccessToken.for_user`; lifetime 30 days (`SIMPLE_JWT` in `config/settings.py`) because refresh is :todo.
- `admin.py` also re-registers `auth.Group` and DRF's `TokenProxy` with the unfold base.

## Tests
`uv run pytest tests/test_conventions.py` (profile, JWT, token, demo auth); 401 on every endpoint: `tests/test_isolation.py`
