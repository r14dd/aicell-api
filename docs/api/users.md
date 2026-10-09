# API — users `/api/users/`

| Method | Path | Status | Purpose |
|---|---|---|---|
| POST | `otp/send/` | `ready` | Send an OTP to an MSISDN |
| POST | `otp/verify/` | `ready` | Verify the code, issue JWT pair |
| POST | `token/refresh/` | `ready` | SimpleJWT refresh |
| POST | `logout/` | `:todo` | Blacklist refresh token (More → Sign out) |
| GET | `me/` | `ready` | Subscriber profile shown on Home and More |
| PATCH | `me/` | `:todo` | Profile settings |
| GET | `me/app-settings/` | `:todo` | Theme, language, push |
| PATCH | `me/app-settings/` | `:todo` | |
| POST | `devices/` | `:todo` | Register push token |

No SMS is sent yet: the code is always `000000` (`OTP_TEST_CODE`), so every
subscriber signs in with the number alone and sees only their own data.

## `POST otp/send/` `ready`

```json
→ { "msisdn": "994516643342" }
← 200 { "request_id": "f1c2…", "ttl": 300, "resend_after": 60 }
← 404 { "code": "not_found", "detail": "No subscriber with this number" }
← 429 { "code": "rate_limited", "detail": "Try again in 60 seconds" }
```

## `POST otp/verify/` `ready`

```json
→ { "request_id": "f1c2…", "code": "000000" }
← 200 { "access": "<jwt>", "refresh": "<jwt>", "subscriber": { …same as me/… } }
← 400 { "code": "invalid_code", "detail": "Wrong code", "attempts_left": 4 }
```

## `POST token/refresh/` `ready`

```json
→ { "refresh": "<jwt>" }
← 200 { "access": "<jwt>" }
← 400 { "code": "invalid_token", "detail": "The refresh token is invalid or has expired" }
```

The access token lives 30 days, the refresh token 90.

## `GET me/` `ready`

```json
← 200 {
  "id": 1,
  "msisdn": "994516643342",
  "display_msisdn": "051 664 33 42",
  "display_name": "Qüdrət Abidzadə",
  "line_type": "prepaid",
  "language": "en",
  "app_version": "Version 5.1.0 (13557)",
  "is_premium": false
}
```

`app_version` is echoed from `X-App-Version` for the More tab footer.

## `GET/PATCH me/app-settings/` `:todo`

```json
{ "theme": "dark", "language": "en", "push": true }
```

## `POST devices/` `:todo`

```json
→ { "platform": "ios", "token": "<expo-push-token>" }
← 201 { "id": 7 }
```
