from decimal import Decimal

import pytest

from api.assistant.models import Conversation
from api.assistant.sse import chunks
from api.billing import services as billing


@pytest.fixture(autouse=True)
def _no_stream_delay(settings):
    settings.ASSISTANT_STREAM_DELAY = 0


@pytest.fixture
def conversation(client):
    res = client.post_json("/api/assistant/conversations/", {})
    assert res.status_code == 201
    return res.json()["id"]


def ask(client, conversation, text, accept="application/json"):
    return client.post_json(
        f"/api/assistant/conversations/{conversation}/messages/",
        {"content": text},
        HTTP_ACCEPT=accept,
    )


def test_balance_question_routes_to_balance(client, subscriber, conversation):
    billing.top_up(subscriber, "card", Decimal("4.00"))
    body = ask(client, conversation, "What is my balance?").json()
    assert body["message"]["route"] == "balance"
    assert "4.00 ₼" in body["message"]["content"]
    assert body["action"]["to"] == "/top-up"


def test_unknown_question_falls_back(client, conversation):
    assert ask(client, conversation, "tell me a joke").json()["message"]["route"] == "fallback"


def test_stream_has_the_documented_events(client, conversation):
    res = ask(client, conversation, "roaming?", accept="text/event-stream")
    assert res["Content-Type"] == "text/event-stream"
    text = b"".join(res.streaming_content).decode()
    for name in ("message", "action", "log", "done"):
        assert f"event: {name}\n" in text


def test_history_is_oldest_first_and_private(client, conversation):
    ask(client, conversation, "balance")
    body = client.get(f"/api/assistant/conversations/{conversation}/messages/").json()
    assert [m["role"] for m in body["results"]] == ["user", "assistant"]
    other = Conversation.objects.create(subscriber=_other())
    assert client.get(f"/api/assistant/conversations/{other.id}/messages/").status_code == 404


def _other():
    from api.users.models import Subscriber

    return Subscriber.objects.create_user("994500000001")


def test_rate_limit(client, conversation, settings):
    settings.ASSISTANT_RATE_LIMIT = 2
    assert ask(client, conversation, "a").status_code == 201
    assert ask(client, conversation, "b").status_code == 201
    assert ask(client, conversation, "c").status_code == 429


def test_rating_clears_the_prompt(client, conversation):
    Conversation.objects.filter(id=conversation).update(status="closed", unread=True)
    item = client.get("/api/assistant/inbox/").json()["items"][0]
    assert item["kind"] == "rate_prompt"
    assert (
        client.post_json(
            f"/api/assistant/conversations/{conversation}/rate/", {"stars": 5}
        ).status_code
        == 201
    )
    assert client.get("/api/assistant/inbox/").json()["items"][0]["kind"] == "conversation"
    assert (
        client.post_json(
            f"/api/assistant/conversations/{conversation}/rate/", {"stars": 9}
        ).status_code
        == 400
    )


def test_chunks_join_back():
    text = "Your balance is 4.00 ₼. Top up?"
    assert "".join(chunks(text)) == text
