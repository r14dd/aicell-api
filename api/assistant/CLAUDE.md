# api/assistant

Support conversations. Status `:dummy`: everything works end to end, answers come from a keyword responder, no model is called. Docs: `docs/api/assistant.md`.

## Models
- `Conversation` — per subscriber; `status` open / closed, `unread`, rating (`stars`, `comment`). `external_id` is `#<id>`.
- `Message` — `role` user / assistant, `content`, and for answers `route`, `action` (JSON), token/cost/latency fields.

## Endpoints (`/api/assistant/`)
| Method | Path | Status |
|---|---|---|
| GET | `inbox/`, `conversations/`, `conversations/<id>/messages/` | :dummy |
| POST | `conversations/`, `conversations/<id>/messages/`, `conversations/<id>/rate/` | :dummy |
| POST | `feedback/` | :todo |

## Not obvious from the code
- The responder is `settings.ASSISTANT_RESPONDER` (default `api.assistant.responder.respond`), signature `respond(subscriber, text) -> Reply(text, route, action, tokens_in, tokens_out, cost)`. A model-backed one plugs in there; `services.send_turn` stores whatever it returns.
- `responder.py` matches substrings in order (first match wins) across en/az/ru keywords and answers in English only. It replaces `İ` before `.lower()` because Python lowercases it to `i` + combining dot.
- `POST .../messages/` streams SSE (`sse.py`: `message`, unnamed text chunks, optional `action`, `log`, `done`); with `Accept: application/json` (and no `text/event-stream`) it returns one 201 body. The view is `route(..., accept_any=True)` so the SSE `Accept` header is not rejected with 406.
- The answer is fully computed and saved before streaming starts; `ASSISTANT_STREAM_DELAY` only paces the chunks.
- Rate limit: 20 user messages per minute per subscriber, counted from `Message` rows in `services._check_rate_limit` (429), separate from `api/common/throttling.py`.
- Inbox `kind` is `rate_prompt` while a conversation is closed and unrated; rating it or (otherwise) opening its history clears `unread`. No endpoint closes a conversation.
- The seeded conversation has the explicit id `3513323` (`api/seeding/subscriber.py`), which then advances the PostgreSQL sequence.
- Conversations and messages are read-only in the admin.

## Tests
`uv run pytest tests/test_assistant.py`
