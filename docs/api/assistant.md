# API — assistant `/api/assistant/` `:dummy`

All endpoints work end to end; answers come from the dummy responder
(`api/assistant/responder.py`, swapped through `ASSISTANT_RESPONDER`).

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `inbox/` | `:dummy` | Support screen: greeting, unread badge, conversation cards |
| GET | `conversations/` | `:dummy` | Subscriber's conversations |
| POST | `conversations/` | `:dummy` | Start a conversation ("Ask a question") |
| GET | `conversations/<id>/messages/` | `:dummy` | History |
| POST | `conversations/<id>/messages/` | `:dummy` | Send a turn, SSE stream back |
| POST | `conversations/<id>/rate/` | `:dummy` | "Rate your conversation" |
| POST | `feedback/` | `:todo` | "Share your ideas for new features" |

Rate limit: 20 messages per minute per subscriber (`429 rate_limited`).

## `GET inbox/`

```json
← 200 { "greeting": "How can we support you?", "unread": 1,
  "items": [ { "conversation_id": 3513323, "external_id": "#3513323", "title": "Rate your conversation", "by": "AI Chat Bot", "last_message_at": "…", "unread": true, "kind": "rate_prompt" } ],
  "actions": [ { "key": "ask", "title": "Ask a question", "body": "We're here to help, just ask away!" },
               { "key": "ideas", "title": "Share your ideas for new features", "body": "Your feedback helps us improve!" } ] }
```

## `POST conversations/`

```json
→ { "source": "mobile" }
← 201 { "id": 3513324, "external_id": "#3513324", "status": "open", "created_at": "…" }
```

## `GET conversations/<id>/messages/`

```json
← 200 { "results": [ { "id": 812, "role": "user", "content": "How much internet do I have left?", "created_at": "…" },
                     { "id": 813, "role": "assistant", "content": "You have 7.20 GB left until 25 October.", "route": "usage", "created_at": "…" } ], "next": null }
```

## `POST conversations/<id>/messages/` (SSE)

Request:

```json
→ { "content": "How much internet do I have left?", "source": "mobile" }
```

Response `text/event-stream` (`Cache-Control: no-cache`, `X-Accel-Buffering: no`):

```
event: message
data: {"message_id": 812, "role": "user"}

data: {"text": "You have "}
data: {"text": "7.20 GB "}
data: {"text": "left until 25 October."}

event: action
data: {"action": "navigate", "to": "/remaining-balance", "label": "Open remaining balance"}

event: log
data: {"message_id": 813, "route": "usage", "tokens_in": 0, "tokens_out": 0, "cost": 0, "latency_ms": 420}

event: done
data: {}
```

Clients that cannot consume SSE may send `Accept: application/json` and
get the full assistant message in one `201` body instead.

## `POST conversations/<id>/rate/`

```json
→ { "stars": 4, "comment": "" }
← 201 { "message": "Thanks! Your rating helps us a lot" }
```

## `POST feedback/` `:todo`

```json
→ { "text": "…" }
← 501 { "code": "not_implemented", "detail": "Support messages are not part of this prototype yet" }
```
