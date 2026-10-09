# API — sim `/api/sim/`

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `` (root) | `ready` | SIM settings overview (badge, dates, rows) |
| GET | `line/` | `ready` | Line settings page |
| PATCH | `line/` | `ready` | Toggle mobile internet / second line |
| POST | `line/internet-settings/` | `:todo` | "Request automatic internet settings" |
| GET | `line/status/` | `ready` | Line status page |
| POST | `line/close/` | `:todo` | "Close line" |
| GET | `call-forwarding/` | `ready` | Four toggles |
| PATCH | `call-forwarding/` | `ready` | Update; "all" wins |
| GET | `roaming/` | `ready` | Roaming toggle state + texts (packs come from `/api/packs/roaming/`) |
| PATCH | `roaming/` | `ready` | Enable / disable roaming |
| GET | `roaming/countries/?q=` | `:todo` | Country pricing search |
| GET | `sms/` | `ready` | SMS language + toggles |
| PATCH | `sms/` | `ready` | Update |
| GET | `puk/` | `ready` | PUK 1 / PUK 2 and copy |
| GET | `services/` | `ready` | Services list |
| GET | `services/<slug>/` | `ready` | Service detail |
| POST | `services/<slug>/subscribe/` | `ready` | "Subscribe for 0.90 ₼" (+ optional "Xəbər ver") |
| POST | `services/<slug>/deactivate/` | `:todo` | "Deactivate" |
| GET | `esim/` | `ready` | eSIM info page content |
| POST | `esim/transfer/` | `:todo` | Transfer to eSIM (Asan İmza) |
| POST | `esim/recover/` | `:todo` | Recover eSIM (code + number) |

## `GET /api/sim/`

```json
← 200 { "msisdn": "994516643342", "lte_enabled": true, "badge": "4G (LTE) enabled",
  "details": [ { "label": "One-way blocking", "value": "2026-10-25" }, { "label": "Deactivation date", "value": "2027-01-23" } ],
  "rows": [ { "key": "line", "label": "Line settings", "deep_link": "/sim/line" }, { "key": "roaming", "label": "Roaming settings", "deep_link": "/sim/roaming" },
            { "key": "esim", "label": "eSIM", "deep_link": "/esim" }, { "key": "sms", "label": "SMS settings", "deep_link": "/sim/sms" },
            { "key": "puk", "label": "PUK codes", "deep_link": "/sim/puk" }, { "key": "services", "label": "Services", "deep_link": "/sim/services" } ] }
```

## `GET line/` / `PATCH line/`

```json
← 200 { "status": "open", "status_title": "Line status: Open", "status_sub": "Line activation/suspension at subscriber’s request",
       "mobile_internet": true, "second_line": true, "call_forwarding_status": "Off",
       "texts": { "second_line_sub": "With call holding you can hold the first caller on the line and answer the second call",
                  "internet_settings_link": "Request automatic internet settings" } }
→ PATCH { "mobile_internet": false }
← 200 { …updated… }
```

## `GET line/status/`

```json
← 200 { "title": "Line status: Open", "general": "You can activate or suspend your line upon request. The line can be closed for a maximum of 90 days",
       "fee": "20.00", "suspend_until": "2027-01-23",
       "consequences": [ "Your agreement will be automatically terminated", "Your line will be completely deactivated", "Remaining balance will be lost", "The number may be reassigned to another person" ],
       "cta": "Close line" }
```

## `GET/PATCH call-forwarding/`

```json
← 200 { "all": false, "unanswered": false, "busy": false, "unreachable": false }
→ PATCH { "all": true }
← 200 { "all": true, "unanswered": false, "busy": false, "unreachable": false }
```

Server rule: `all=true` resets the other three; a PATCH setting one of the
three while `all=true` returns `400 validation_error`.

## `GET/PATCH roaming/`

```json
← 200 { "enabled": false, "changed_at": null, "texts": { "search_title": "Search for country pricing", "search_placeholder": "Explore countries and tariffs", "packs_title": "Roaming packs" } }
→ PATCH { "enabled": true }
← 200 { "enabled": true, "changed_at": "…" }
```

## `GET/PATCH sms/`

```json
← 200 { "language": "az", "languages": [ { "id": "az", "name": "Azerbaijani" }, { "id": "en", "name": "English" } ],
       "toggles": { "ads": true, "campaigns": true, "partners": true } }
→ PATCH { "language": "en", "toggles": { "partners": false } }
```

## `GET puk/`

```json
← 200 { "codes": [ { "label": "PUK 1", "value": "5839 0447" }, { "label": "PUK 2", "value": "8815 4421" } ],
       "paragraphs": [ [ { "text": "After 3 incorrect entries of PIN 1 and PIN 2, the codes " }, { "text": "will be blocked", "bold": true }, … ], [ … ] ] }
```

## `GET services/` / `GET services/<slug>/`

List rows: `id`, `name`, `sub`, `period` ("30 days"), `price` (null when
activated), `activated`, `badge` (`AUTO-RENEWAL` / `ACTIVATED`). Detail
returns `sections` in the `ServiceSection` shape of
`src/data/simServices.ts` (`text`, `rows`, `option`) and `action`.

## `POST services/<slug>/subscribe/`

```json
→ { "options": ["xeber-ver"] }
← 201 { "subscription": { "id": 3, "service": "missed-call", "status": "active", "next_payment_at": "…" },
       "transaction": { "title": "Buraxılmış zəng service", "amount": "-0.90" }, "balance": "…" }
← 402 { "code": "insufficient_balance", "detail": "Not enough balance for this service" }
← 409 { "code": "already_active" }
```

## `GET esim/`

```json
← 200 { "benefits": [ { "key": "safe", "title": "Safe & Reliable", "body": "Your eSIM stays secure, no physical card to lose or damage" }, { "key": "flexible", … }, { "key": "eco", … } ],
       "asan_note": "The use of the obtained eSIM “Asan İmza” service is possible only after …",
       "actions": [ { "key": "transfer", "label": "Transfer to eSIM" }, { "key": "recover", "label": "Recover eSIM", "deep_link": "/esim/recover" } ] }
```

## `POST esim/transfer/` `:todo`, `POST esim/recover/` `:todo`

```json
→ transfer { "asan_phone": "994516643342", "asan_user_id": "…" }
→ recover  { "code": "ABCD-1234", "msisdn": "994516643342" }
← 501 { "code": "not_implemented", "detail": "eSIM recovery is not part of this prototype yet" }
```
