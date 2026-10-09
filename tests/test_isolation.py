"""A subscriber sees and changes only their own data.

Every check runs with two seeded subscribers that own the same kinds of
objects, some of them under the same public id.
"""

import pytest
from rest_framework.exceptions import PermissionDenied

from api.assistant.models import Conversation, Message
from api.common.exceptions import exception_handler
from api.content.models import Notification, StoryView
from api.packs.models import PackActivation
from api.sim.models import ServiceSubscription

from .conftest import OTHER_CONVERSATION_ID, OTHER_MSISDN
from .test_docs_conformance import ROWS

# Values that exist only in the other subscriber's data.
OTHER_MARKERS = [
    OTHER_MSISDN,
    "050 000 00 02",
    "Other Person",
    "99.99",
    "9999",
    "other_steam",
    "zz99ZZ",
    "1111 2222",
    "3333 4444",
    str(OTHER_CONVERSATION_ID),
    "only-other",
]

READS = [row for row in ROWS if row[0] == "GET" and row[2] != ":todo"]
PUBLIC = {"/api/users/otp/send/", "/api/users/otp/verify/", "/api/users/token/refresh/"}


@pytest.fixture
def other_notification(other):
    return Notification.objects.create(
        subscriber=other, slug="only-other", title="Only for the other", body="Private"
    )


@pytest.mark.parametrize("method,path,status", READS)
def test_reads_never_contain_another_subscribers_data(
    client, other, other_notification, method, path, status
):
    response = client.get(path)
    assert response.status_code == 200
    body = response.content.decode()
    leaked = [marker for marker in OTHER_MARKERS if marker in body]
    assert not leaked, f"{path} leaked {leaked}"


@pytest.mark.parametrize("method,path,status", READS)
def test_each_subscriber_gets_their_own_answer(client, other_client, method, path, status):
    """The other subscriber is served too, and with their own values."""
    response = other_client.get(path)
    # The demo conversation in the path belongs to the first subscriber.
    expected = 404 if "/conversations/3513323/" in path else 200
    assert response.status_code == expected
    assert "wa16Kg" not in response.content.decode()


def test_objects_of_another_subscriber_answer_404(client, other, other_notification):
    foreign = f"/api/assistant/conversations/{OTHER_CONVERSATION_ID}"
    attempts = [
        client.get("/api/content/notifications/only-other/"),
        client.post_json("/api/content/notifications/only-other/read/"),
        client.get(f"{foreign}/messages/"),
        client.post_json(f"{foreign}/messages/", {"content": "hi"}),
        client.post_json(f"{foreign}/rate/", {"stars": 5}),
    ]
    for response in attempts:
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"

    other_notification.refresh_from_db()
    conversation = Conversation.objects.get(id=OTHER_CONVERSATION_ID)
    assert other_notification.read_at is None
    assert conversation.stars is None
    assert Message.objects.filter(conversation=conversation).count() == 2


def test_an_existing_and_a_missing_object_are_indistinguishable(client, other):
    """404 for both, with the same body: ids of other subscribers cannot be probed."""
    foreign = client.get(f"/api/assistant/conversations/{OTHER_CONVERSATION_ID}/messages/")
    missing = client.get("/api/assistant/conversations/999999999/messages/")
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


def test_writes_change_only_the_callers_data(client, other, other_client):
    """The same public ids exist for both subscribers; only the caller's rows move."""
    before = {
        "balance": other_client.get("/api/billing/balance/").json(),
        "transactions": other_client.get("/api/billing/transactions/").json(),
        "sim": other_client.get("/api/sim/line/").json(),
        "forwarding": other_client.get("/api/sim/call-forwarding/").json(),
        "roaming": other_client.get("/api/sim/roaming/").json(),
        "sms": other_client.get("/api/sim/sms/").json(),
        "stories": other_client.get("/api/content/stories/").json(),
        "notifications": other_client.get("/api/content/notifications/").json(),
        "services": other_client.get("/api/sim/services/").json(),
        "steam": other_client.get("/api/billing/steam/accounts/").json(),
        "inbox": other_client.get("/api/assistant/inbox/").json(),
    }

    writes = [
        client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "50.00"}),
        client.pay("/api/billing/steam/top-up/", {"account": "mine", "amount": "5.00", "save": 1}),
        client.pay("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"}),
        client.pay("/api/packs/social/tehsil/activate/", {"plan_id": "10gb"}),
        client.pay("/api/packs/roaming/purchase/", {"pack_id": "r-500mb"}),
        client.pay("/api/sim/services/missed-call/subscribe/", {}),
        client.patch_json("/api/sim/line/", {"mobile_internet": False, "second_line": False}),
        client.patch_json("/api/sim/call-forwarding/", {"all": True}),
        client.patch_json("/api/sim/roaming/", {"enabled": True}),
        client.patch_json("/api/sim/sms/", {"language": "en", "toggles": {"ads": False}}),
        client.post_json("/api/content/stories/gift-wheel/viewed/"),
        client.post_json("/api/content/notifications/wingz/read/"),
        client.post_json("/api/content/app-rating/", {"stars": 5}),
        client.post_json("/api/assistant/conversations/"),
    ]
    assert [response.status_code for response in writes] == [201] * 6 + [200] * 6 + [201] * 2

    after = {
        key: other_client.get(path).json()
        for key, path in {
            "balance": "/api/billing/balance/",
            "transactions": "/api/billing/transactions/",
            "sim": "/api/sim/line/",
            "forwarding": "/api/sim/call-forwarding/",
            "roaming": "/api/sim/roaming/",
            "sms": "/api/sim/sms/",
            "stories": "/api/content/stories/",
            "notifications": "/api/content/notifications/",
            "services": "/api/sim/services/",
            "steam": "/api/billing/steam/accounts/",
            "inbox": "/api/assistant/inbox/",
        }.items()
    }
    assert after == before
    for model in (PackActivation, ServiceSubscription, StoryView):
        assert not model.objects.filter(subscriber=other).exists()


def test_an_idempotency_key_belongs_to_the_subscriber_who_used_it(client, other_client):
    """The same key from two subscribers is two requests, not a replay of the first."""
    key = "5f0c2b9e-7a54-4c2b-9d0e-1f3a5b7c9d11"
    data = {"card_bin": "416300", "amount": "10.00"}
    mine = client.pay("/api/billing/top-up/card/", data, key=key).json()
    theirs = other_client.pay("/api/billing/top-up/card/", data, key=key).json()
    assert mine["balance"] == "26.21"
    assert theirs["balance"] == "109.99"


# --- 401 and 403 ------------------------------------------------------------


@pytest.mark.parametrize("method,path,status", [row for row in ROWS if row[1] not in PUBLIC])
def test_every_endpoint_requires_credentials(anon, catalogue, method, path, status):
    response = anon.generic(method, path, "{}", content_type="application/json")
    assert response.status_code == 401, f"{method} {path}"
    assert response.json() == {"code": "not_authenticated", "detail": "Authentication required"}
    assert response["WWW-Authenticate"].startswith("Bearer")


@pytest.mark.parametrize("path", sorted(PUBLIC))
def test_sign_in_endpoints_are_public(anon, path):
    assert anon.post_json(path).status_code == 400  # reaches validation, not 401


def test_an_inactive_subscriber_is_rejected(anon, subscriber):
    from rest_framework_simplejwt.tokens import AccessToken

    token = AccessToken.for_user(subscriber)
    subscriber.is_active = False
    subscriber.save()
    response = anon.get("/api/users/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_forbidden_uses_the_shared_error_shape():
    response = exception_handler(PermissionDenied(), {})
    assert response.status_code == 403
    assert response.data["code"] == "forbidden"
    assert set(response.data) == {"code", "detail"}
