# api/sim

SIM settings (line, call forwarding, roaming, SMS, PUK, eSIM) and paid services. Docs: `docs/api/sim.md`.

## Models
- `SimProfile` — one per subscriber: every toggle, the dates, PUK codes.
- `ServiceSubscription` — a paid service the subscriber has; `service` is a catalogue slug, not an FK.
- `SimService` — catalogue (`CatalogueItem`, translated); `sections` JSON holds the detail page.

## Endpoints (`/api/sim/`)
| Method | Path | Status |
|---|---|---|
| GET | `` (root), `line/`, `line/status/`, `call-forwarding/`, `roaming/`, `sms/`, `puk/`, `services/`, `services/<slug>/`, `esim/` | ready |
| PATCH | `line/`, `call-forwarding/`, `roaming/`, `sms/` | ready |
| POST | `services/<slug>/subscribe/` | ready, money |
| POST | `line/internet-settings/`, `line/close/`, `services/<slug>/deactivate/`, `esim/transfer/`, `esim/recover/` | :todo |
| GET | `roaming/countries/` | :todo |

## Not obvious from the code
- Call forwarding (`services.update_call_forwarding`): `all=true` resets the other three; while `all` is on, turning one on without also sending `all=false` is 400.
- `subscribe` charges via `billing.services.charge` and is single-instance: an active subscription → 409, checked under `billing.lock_wallet`. Allowed `options` are the `option.id` values inside `SimService.sections`.
- `services/` rows: `price` becomes `null` and `badge` "ACTIVATED" once subscribed; the subscription state is per subscriber and never cached, the service list (`catalogue.services`) is.
- A subscriber without a `SimProfile` gets 404 from every endpoint here (`services.sim_of`).
- All fixed screen copy (rows, texts, PUK paragraphs, eSIM page) is in `texts.py` as lazy strings; PUK text is split into segments so the bold part can be marked.
- `roaming/` here is only the toggle (`changed_at` moves only on a real change); roaming packs are `api/packs/`.
- `ServiceSubscription` is read-only in the admin.

## Tests
`uv run pytest tests/test_sim.py`
