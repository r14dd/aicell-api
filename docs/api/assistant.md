# API — assistant `/api/assistant/` `:dummy`

All endpoints work end to end. With `GEMINI_API_KEY` set, Gemini routes each message, the answer
is built from the subscriber's data or the Milvus knowledge base and written by Gemini
(`api/assistant/agent.py`); without it the keyword responder answers (`api/assistant/responder.py`).
`ASSISTANT_RESPONDER` picks which.

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `inbox/` | `:dummy` | Support screen: greeting, unread badge, conversation cards |
| GET | `conversations/` | `:dummy` | Subscriber's conversations |
| POST | `conversations/` | `:dummy` | Start a conversation ("Ask a question") |
| GET | `conversations/<id>/messages/` | `:dummy` | History |
| POST | `conversations/<id>/messages/` | `:dummy` | Send a turn, SSE stream back |
| POST | `conversations/<id>/voice/` | `:dummy` | Send a voice message, spoken answer back |
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

## `POST conversations/<id>/voice/`

`multipart/form-data` with an `audio` file (wav, mp3, m4a, ogg or webm, up to 5 MB). Speech to text,
the same answer as a text message, then the answer as speech (all Gemini).

```json
→ audio=<file>
← 201 { "transcript": "Balansım nə qədərdir?", "user_message_id": 812,
        "message": { "id": 813, "role": "assistant", "content": "Balansınız 16.21 ₼-dir.", "route": "balance", "created_at": "…" },
        "action": { "action": "navigate", "to": "/top-up", "label": "Top up balance" },
        "audio": "<base64 WAV, 24 kHz mono>", "audio_mime": "audio/wav" }
```

`audio` is `null` when speech synthesis failed; the text is still there. An unintelligible
recording answers `400`.

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
