import json

import pytest

from api.assistant import responder
from api.assistant.models import Message
from api.seeding import DEMO_CONVERSATION_ID

SEEDED = f"/api/assistant/conversations/{DEMO_CONVERSATION_ID}"


def events(response):
    """Parse an SSE body into (event, data) pairs; unnamed events are `None`."""
    body = b"".join(response.streaming_content).decode()
    parsed = []
    for block in body.strip().split("\n\n"):
        event, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        parsed.append((event, data))
    return parsed


def start(client):
    return client.post_json("/api/assistant/conversations/", {"source": "mobile"}).json()["id"]


def test_inbox_shows_the_rate_prompt(client):
    body = client.get("/api/assistant/inbox/").json()
    assert body["greeting"] == "How can we support you?"
    assert body["unread"] == 1
    assert body["items"][0] == {
        "conversation_id": DEMO_CONVERSATION_ID,
        "external_id": f"#{DEMO_CONVERSATION_ID}",
        "title": "Rate your conversation",
        "by": "AI Chat Bot",
        "last_message_at": "2026-10-06T14:01:00Z",
        "unread": True,
        "kind": "rate_prompt",
    }
    assert [action["key"] for action in body["actions"]] == ["ask", "ideas"]


def test_rating_clears_the_prompt(client):
    response = client.post_json(f"{SEEDED}/rate/", {"stars": 4, "comment": ""})
    assert response.status_code == 201
    assert response.json() == {"message": "Thanks! Your rating helps us a lot"}
    body = client.get("/api/assistant/inbox/").json()
    assert body["unread"] == 0
    assert body["items"][0]["kind"] == "conversation"
    assert client.post_json(f"{SEEDED}/rate/", {"stars": 0}).status_code == 400


def test_start_conversation_continues_the_id_sequence(client):
    response = client.post_json("/api/assistant/conversations/", {"source": "mobile"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == DEMO_CONVERSATION_ID + 1
    assert body["external_id"] == f"#{DEMO_CONVERSATION_ID + 1}"
    assert body["status"] == "open"
    assert len(client.get("/api/assistant/conversations/").json()["results"]) == 2


def test_history(client):
    body = client.get(f"{SEEDED}/messages/").json()
    assert [m["role"] for m in body["results"]] == ["user", "assistant"]
    assert body["results"][1]["route"] == "usage"
    assert "route" not in body["results"][0]
    assert body["next"] is None


def test_send_streams_sse_in_the_documented_order(client):
    conversation = start(client)
    response = client.post(
        f"/api/assistant/conversations/{conversation}/messages/",
        {"content": "How much internet do I have left?", "source": "mobile"},
        format="json",
        HTTP_ACCEPT="text/event-stream",
    )
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert response["Cache-Control"] == "no-cache"
    assert response["X-Accel-Buffering"] == "no"

    stream = events(response)
    names = [event for event, _ in stream]
    assert names[0] == "message" and names[-3:] == ["action", "log", "done"]
    assert all(name is None for name in names[1:-3])

    text = "".join(data["text"] for event, data in stream if event is None)
    assert text == "You have 7.20 GB left until 25 October."
    assert stream[0][1]["role"] == "user"
    assert stream[-3][1] == {
        "action": "navigate",
        "to": "/remaining-balance",
        "label": "Open remaining balance",
    }
    log = stream[-2][1]
    assert log["route"] == "usage" and log["message_id"] == stream[0][1]["message_id"] + 1
    assert set(log) == {"message_id", "route", "tokens_in", "tokens_out", "cost", "latency_ms"}
    assert stream[-1][1] == {}

    history = client.get(f"/api/assistant/conversations/{conversation}/messages/").json()["results"]
    assert [m["content"] for m in history] == ["How much internet do I have left?", text]


def test_send_with_accept_json_returns_one_body(client):
    conversation = start(client)
    response = client.post(
        f"/api/assistant/conversations/{conversation}/messages/",
        {"content": "What is my balance?"},
        format="json",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"] == "Your balance is 16.21 ₼."
    assert body["message"]["route"] == "balance"
    assert body["action"]["to"] == "/top-up"


def test_answers_use_live_subscriber_data(client):
    conversation = start(client)
    client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "10.00"})
    response = client.post(
        f"/api/assistant/conversations/{conversation}/messages/",
        {"content": "balans"},
        format="json",
        HTTP_ACCEPT="application/json",
    )
    assert response.json()["message"]["content"] == "Your balance is 26.21 ₼."


@pytest.mark.parametrize(
    "text,route",
    [
        ("How much internet do I have left?", "usage"),
        ("İnternet qalığım nə qədərdir?", "usage"),
        ("What is my number balance?", "balance"),
        ("Which tariff am I on?", "tariff"),
        ("Show me internet packs", "packs"),
        ("How do I turn on roaming?", "roaming"),
        ("I need a kredit", "kredit"),
        ("Which tariff suits me?", "recommendation"),
        ("Mənə hansı paket uyğundur?", "recommendation"),
        ("Какой тариф мне подходит?", "recommendation"),
        ("Tell me a joke", "fallback"),
    ],
)
def test_dummy_responder_routes(subscriber, text, route):
    assert responder.respond(subscriber, text).route == route


def test_fallback_has_no_action_event(client):
    conversation = start(client)
    response = client.post(
        f"/api/assistant/conversations/{conversation}/messages/",
        {"content": "Tell me a joke"},
        format="json",
    )
    assert [event for event, _ in events(response) if event] == ["message", "log", "done"]


def test_rate_limit_is_20_messages_per_minute(client):
    conversation = start(client)
    url = f"/api/assistant/conversations/{conversation}/messages/"
    for _ in range(20):
        assert (
            client.post(
                url, {"content": "hi"}, format="json", HTTP_ACCEPT="application/json"
            ).status_code
            == 201
        )
    limited = client.post(url, {"content": "hi"}, format="json", HTTP_ACCEPT="application/json")
    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"
    assert Message.objects.filter(conversation_id=conversation, role="user").count() == 20


def test_other_subscribers_conversations_are_not_reachable(client, subscriber):
    from api.assistant.models import Conversation
    from api.users.models import Subscriber

    other = Subscriber.objects.create_user("994500000000")
    foreign = Conversation.objects.create(subscriber=other)
    assert client.get(f"/api/assistant/conversations/{foreign.id}/messages/").status_code == 404
    assert (
        client.post_json(
            f"/api/assistant/conversations/{foreign.id}/messages/", {"content": "hi"}
        ).status_code
        == 404
    )


def test_empty_message_is_rejected(client):
    conversation = start(client)
    response = client.post_json(
        f"/api/assistant/conversations/{conversation}/messages/", {"content": ""}
    )
    assert response.status_code == 400


def probe(subscriber, content):
    from django.db import connection

    probe.depth = len(connection.savepoint_ids)
    return responder.respond(subscriber, content)


def test_responder_runs_outside_the_turn_transaction(client, settings):
    from django.db import connection

    settings.ASSISTANT_RESPONDER = "tests.test_assistant.probe"
    depth = len(connection.savepoint_ids)
    conversation_id = start(client)
    response = client.post(
        f"/api/assistant/conversations/{conversation_id}/messages/",
        {"content": "hi", "source": "mobile"},
        format="json",
        HTTP_ACCEPT="text/event-stream",
    )
    events(response)
    assert probe.depth == depth


def test_inbox_query_count_does_not_grow_with_conversations(client, django_assert_max_num_queries):
    from api.assistant.models import Conversation

    owner = Conversation.objects.get(id=DEMO_CONVERSATION_ID).subscriber
    for _ in range(60):
        conversation = Conversation.objects.create(subscriber=owner)
        Message.objects.create(conversation=conversation, role="user", content="hi")
    with django_assert_max_num_queries(8):
        body = client.get("/api/assistant/inbox/").json()
    assert len(body["items"]) == 50


# --- voice and the Gemini responder (Gemini itself is always faked) ---------


def _wav():
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile("q.wav", b"RIFFxxxxWAVE", content_type="audio/wav")


def test_voice_message_returns_transcript_answer_and_audio(client, monkeypatch):
    from api.assistant import gemini

    monkeypatch.setattr(gemini, "transcribe", lambda audio, mime: "how much internet is left")
    monkeypatch.setattr(gemini, "speak", lambda text: b"WAVDATA")
    conversation = start(client)
    response = client.post(
        f"/api/assistant/conversations/{conversation}/voice/", {"audio": _wav()}, format="multipart"
    )
    body = response.json()
    assert response.status_code == 201, body
    assert body["transcript"] == "how much internet is left"
    assert body["message"]["route"] == "usage"
    assert body["audio"] == "V0FWREFUQQ=="
    stored = client.get(f"/api/assistant/conversations/{conversation}/messages/").json()
    assert [m["role"] for m in stored["results"]] == ["user", "assistant"]


def test_voice_message_survives_speech_synthesis_failure(client, monkeypatch):
    from api.assistant import gemini

    def broken(text):
        raise gemini.GeminiError("down")

    monkeypatch.setattr(gemini, "transcribe", lambda audio, mime: "balance")
    monkeypatch.setattr(gemini, "speak", broken)
    response = client.post(
        f"/api/assistant/conversations/{start(client)}/voice/",
        {"audio": _wav()},
        format="multipart",
    )
    assert response.status_code == 201
    assert response.json()["audio"] is None


def test_unintelligible_voice_message_is_a_400(client, monkeypatch):
    from api.assistant import gemini

    monkeypatch.setattr(gemini, "transcribe", lambda audio, mime: "")
    response = client.post(
        f"/api/assistant/conversations/{start(client)}/voice/",
        {"audio": _wav()},
        format="multipart",
    )
    assert response.status_code == 400


def test_voice_message_to_a_foreign_conversation_is_a_404(client):
    from api.assistant.models import Conversation
    from api.users.models import Subscriber

    foreign = Conversation.objects.create(subscriber=Subscriber.objects.create_user("994500000001"))
    response = client.post(
        f"/api/assistant/conversations/{foreign.id}/voice/", {"audio": _wav()}, format="multipart"
    )
    assert response.status_code == 404


def test_agent_routes_with_gemini_and_writes_from_facts(subscriber, monkeypatch):
    from api.assistant import agent, gemini

    calls = []

    def fake(system, prompt, *, schema=None):
        calls.append(prompt)
        return ('{"route": "balance"}' if schema else "Balansınız 5 manatdır."), 10, 5

    monkeypatch.setattr(gemini, "generate", fake)
    answer = agent.respond(subscriber, "Balansım nə qədərdir?")
    assert answer.route == "balance"
    assert answer.text == "Balansınız 5 manatdır."
    assert answer.action["to"] == "/top-up"
    assert (answer.tokens_in, answer.tokens_out) == (20, 10)
    assert "Your balance is" in calls[1]  # the model is given the facts, not the question alone


def test_agent_answers_from_knowledge_chunks(subscriber, monkeypatch):
    from api.assistant import agent, gemini, knowledge

    seen = {}

    def fake(system, prompt, *, schema=None):
        seen["prompt"] = prompt
        return ('{"route": "service"}' if schema else "Kod yığın."), 1, 1

    monkeypatch.setattr(gemini, "generate", fake)
    monkeypatch.setattr(
        knowledge, "retrieve", lambda q, kinds: [{"title": "Call forwarding", "text": "Dial *21*"}]
    )
    answer = agent.respond(subscriber, "zəngi yönləndirməni necə qoşum")
    assert answer.route == "service"
    assert "Dial *21*" in seen["prompt"]


def test_agent_falls_back_to_keyword_rules_when_gemini_fails(subscriber, monkeypatch):
    from api.assistant import agent, gemini

    def down(*args, **kwargs):
        raise gemini.GeminiError("down")

    monkeypatch.setattr(gemini, "generate", down)
    assert agent.respond(subscriber, "balance").route == "balance"
