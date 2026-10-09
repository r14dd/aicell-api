"""Server-Sent Events encoding of one assistant turn."""

import json
import time
from collections.abc import Iterator

from django.conf import settings

WORDS_PER_CHUNK = 2


def event(payload: dict, name: str | None = None) -> str:
    prefix = f"event: {name}\n" if name else ""
    return f"{prefix}data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def chunks(text: str) -> list[str]:
    """Split into small pieces that join back to exactly `text`."""
    words = text.split(" ")
    groups = [words[i : i + WORDS_PER_CHUNK] for i in range(0, len(words), WORDS_PER_CHUNK)]
    last = len(groups) - 1
    return [" ".join(group) + ("" if index == last else " ") for index, group in enumerate(groups)]


def stream(turn) -> Iterator[str]:
    """`message`, the text chunks, an optional `action`, then `log` and `done`."""
    reply = turn.reply
    yield event({"message_id": turn.user_message.id, "role": "user"}, "message")
    for chunk in chunks(reply.content):
        if settings.ASSISTANT_STREAM_DELAY:
            time.sleep(settings.ASSISTANT_STREAM_DELAY)
        yield event({"text": chunk})
    if reply.action:
        yield event(reply.action, "action")
    yield event(
        {
            "message_id": reply.id,
            "route": reply.route,
            "tokens_in": reply.tokens_in,
            "tokens_out": reply.tokens_out,
            "cost": float(reply.cost),
            "latency_ms": reply.latency_ms,
        },
        "log",
    )
    yield event({}, "done")
