from api.assistant import llm_responder, responder
from api.assistant.models import Message


def test_matches_the_keyword_responder_until_models_are_connected(subscriber):
    assert llm_responder.respond(subscriber, "balans") == responder.respond(subscriber, "balans")


def test_selected_through_the_setting(client, settings):
    settings.ASSISTANT_RESPONDER = "api.assistant.llm_responder.respond"
    conversation = client.post_json("/api/assistant/conversations/", {"source": "mobile"}).json()[
        "id"
    ]
    response = client.post(
        f"/api/assistant/conversations/{conversation}/messages/",
        {"content": "balans"},
        format="json",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 201
    assert response.json()["message"]["route"] == "balance"
    assert Message.objects.filter(conversation_id=conversation, role="assistant").count() == 1
