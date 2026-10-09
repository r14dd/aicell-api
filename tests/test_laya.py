from types import SimpleNamespace

import pytest

from api.laya import brain, claude

PENDING = {
    "insight_id": 41,
    "task": {"name": "activatePack", "params": {"slug": "youtube", "plan": "5gb"}},
}


def plan(client, text, **context):
    return client.post_json("/api/laya/plan/", {"text": text, "context": context})


def test_screens_and_languages(client):
    body = plan(client, "where can I top up my balance").json()
    assert (body["task"], body["language"]) == ("topUp", "en")
    assert plan(client, "balansımı göstər").json()["task"] == "checkBalance"


def test_unknown_request_does_nothing(client):
    body = plan(client, "bla bla").json()
    assert body["task"] == "none"
    assert body["params"] is None


def test_yes_runs_the_pending_task_unchanged(client):
    body = plan(client, "hə, qoş", pending=PENDING).json()
    assert body["task"] == "activatePack"
    assert body["params"] == {"slug": "youtube", "plan": "5gb", "insight_id": 41}


def test_no_dismisses_and_why_explains(client):
    no = plan(client, "yox, sonra", pending=PENDING).json()
    assert (no["task"], no["params"]) == ("dismissInsight", {"insight_id": 41})
    why = plan(client, "niyə?", pending=PENDING).json()
    assert (why["task"], why["params"]) == ("explainInsight", {"insight_id": 41})


def test_yes_without_pending_asks_what(client):
    body = plan(client, "hə").json()
    assert (body["task"], body["reply"]) == ("none", "Nəyi edim?")


def test_plan_needs_text_and_a_subscriber(client, anon):
    assert client.post_json("/api/laya/plan/", {}).status_code == 400
    assert anon.post_json("/api/laya/plan/", {"text": "hi"}).status_code == 401


def test_narrate_answers_in_the_asked_language(client):
    insight = {"id": 1, "kind": "overage", "evidence": {}, "offers": []}
    for language in ("az", "en"):
        body = client.post_json(
            "/api/laya/narrate/", {"language": language, "insight": insight}
        ).json()
        assert body["language"] == language
        assert body["speech"]
    assert (
        client.post_json("/api/laya/narrate/", {"language": "xx", "insight": insight}).status_code
        == 400
    )


class Brain:
    """A brain that returns what it is told, and counts its calls."""

    def __init__(self, plan=None, narrate=None):
        self.answers = {"plan": plan, "narrate": narrate}
        self.calls = 0

    def plan(self, payload):
        self.calls += 1
        return self.answers["plan"]

    def narrate(self, payload):
        self.calls += 1
        return self.answers["narrate"]


@pytest.fixture
def swap(monkeypatch):
    def use(**answers):
        fake = Brain(**answers)
        monkeypatch.setattr(brain, "_brain", lambda: fake)
        return fake

    return use


def test_a_made_up_price_is_replaced_by_a_safe_answer(client, swap):
    fake = swap(
        plan={
            "reply": "It costs 4.99",
            "task": "buyPack",
            "params": None,
            "amount": None,
            "language": "en",
        }
    )
    body = plan(client, "how much is it", balance=16.21).json()
    assert (body["task"], body["params"]) == ("none", None)
    assert "4.99" not in body["reply"]
    assert fake.calls == 2


def test_numbers_from_the_request_are_allowed(client, swap):
    swap(
        plan={
            "reply": "You have 16.2 left",
            "task": "none",
            "params": None,
            "amount": None,
            "language": "en",
        }
    )
    assert plan(client, "balance", balance=16.20).json()["reply"] == "You have 16.2 left"


def test_a_task_outside_the_catalogue_is_rejected(client, swap):
    swap(
        plan={
            "reply": "ok",
            "task": "wipeAccount",
            "params": None,
            "amount": None,
            "language": "en",
        }
    )
    assert plan(client, "do it").json()["task"] == "none"


def test_narrate_refuses_invented_numbers_and_long_speech(client, swap):
    insight = {"id": 1, "evidence": {"gb": 12}, "offers": []}
    swap(narrate={"speech": "You used 99 GB. Shall I?", "language": "en"})
    wrong = client.post_json("/api/laya/narrate/", {"language": "en", "insight": insight})
    assert (wrong.status_code, wrong.json()["code"]) == (502, "laya_unavailable")
    swap(narrate={"speech": "word " * 46, "language": "en"})
    long = client.post_json("/api/laya/narrate/", {"language": "en", "insight": insight})
    assert long.status_code == 502


def test_a_failing_brain_is_a_502(client, monkeypatch):
    def boom(payload):
        raise RuntimeError("model down")

    monkeypatch.setattr(brain, "_brain", lambda: SimpleNamespace(plan=boom, narrate=boom))
    response = plan(client, "hi")
    assert (response.status_code, response.json()["code"]) == (502, "laya_unavailable")


def test_claude_reads_the_forced_tool_call(settings, monkeypatch):
    seen = {}

    class Messages:
        def create(self, **kwargs):
            seen.update(kwargs)
            block = SimpleNamespace(type="tool_use", input={"speech": "ok", "language": "en"})
            return SimpleNamespace(content=[SimpleNamespace(type="text"), block])

    monkeypatch.setattr(
        claude.anthropic, "Anthropic", lambda **kwargs: SimpleNamespace(messages=Messages())
    )
    answer = claude.narrate({"insight": {}, "language": "en", "name": ""})
    assert answer == {"speech": "ok", "language": "en"}
    assert seen["model"] == settings.LAYA_NARRATE_MODEL
    assert seen["tool_choice"] == {"type": "tool", "name": "answer"}


def test_an_answer_without_params_is_still_an_answer(client, swap):
    swap(plan={"reply": "Açıram.", "task": "openTariff", "language": "az"})
    response = plan(client, "tarifim")
    assert response.status_code == 200
    assert response.json() == {
        "reply": "Açıram.",
        "task": "openTariff",
        "params": None,
        "amount": None,
        "language": "az",
    }


@pytest.mark.parametrize("answer", [None, "Açıram.", ["openTariff"], 7])
def test_an_answer_that_is_not_an_object_is_rejected(client, swap, answer):
    swap(plan=answer, narrate=answer)
    lost = plan(client, "tarifim")
    assert (lost.status_code, lost.json()["task"]) == (200, "none")
    narrated = client.post_json("/api/laya/narrate/", {"insight": {"id": 1}})
    assert narrated.status_code == 502
    assert narrated.json()["code"] == "laya_unavailable"


def test_gemini_top_up_without_an_amount_asks_instead(monkeypatch):
    from api.laya import gemini

    monkeypatch.setattr(
        gemini,
        "_ask",
        lambda *_: {
            "reply": "How much?",
            "task": "topUp",
            "params": None,
            "amount": None,
            "language": "en",
        },
    )
    assert gemini.plan({"text": "top up", "context": {}})["task"] == "none"
