import uuid
from datetime import timedelta

from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import AccessToken

from api.billing.models import Transaction


def test_me_matches_the_documented_shape(client):
    body = client.get("/api/users/me/", HTTP_X_APP_VERSION="5.1.0 (13557)").json()
    assert body == {
        "id": body["id"],
        "msisdn": "994516643342",
        "display_msisdn": "051 664 33 42",
        "display_name": "Qüdrət Abidzadə",
        "line_type": "prepaid",
        "language": "en",
        "app_version": "Version 5.1.0 (13557)",
        "is_premium": False,
    }


def test_no_credentials_is_401_when_demo_auth_is_off(anon, subscriber, settings):
    settings.DEMO_AUTH = False
    response = anon.get("/api/users/me/")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_bearer_jwt_authenticates(anon, subscriber, settings):
    settings.DEMO_AUTH = False
    token = AccessToken.for_user(subscriber)
    response = anon.get("/api/users/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    assert response.json()["msisdn"] == subscriber.msisdn


def test_expired_jwt_is_token_expired(anon, subscriber, settings):
    settings.DEMO_AUTH = False
    token = AccessToken.for_user(subscriber)
    token.set_exp(lifetime=-timedelta(minutes=5))
    response = anon.get("/api/users/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"


def test_service_token_authenticates(anon, subscriber, settings):
    settings.DEMO_AUTH = False
    token = Token.objects.create(user=subscriber)
    response = anon.get("/api/users/me/", HTTP_AUTHORIZATION=f"Token {token.key}")
    assert response.status_code == 200


def test_demo_auth_acts_as_the_seeded_subscriber_only_when_enabled(anon, subscriber, settings):
    settings.DEMO_AUTH = True
    assert anon.get("/api/users/me/").json()["msisdn"] == settings.DEMO_MSISDN
    # an Authorization header always wins over the demo fallback
    assert anon.get("/api/users/me/", HTTP_AUTHORIZATION="Bearer nope").status_code == 401
    settings.DEMO_AUTH = False
    assert anon.get("/api/users/me/").status_code == 401


def test_unknown_path_and_unknown_object_are_json_404(client):
    for path in ("/api/nope/", "/api/packs/social/nope/", "/api/content/notifications/nope/"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


def test_validation_error_lists_errors(client):
    response = client.pay("/api/billing/top-up/card/", {"card_bin": "12", "amount": "25.00"})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation_error"
    assert "card_bin" in body["errors"]


def test_money_post_requires_a_uuid_idempotency_key(client):
    data = {"card_bin": "416300", "amount": "25.00"}
    missing = client.post_json("/api/billing/top-up/card/", data)
    assert missing.status_code == 400
    assert missing.json()["code"] == "validation_error"
    malformed = client.pay("/api/billing/top-up/card/", data, key="not-a-uuid")
    assert malformed.status_code == 400
    assert Transaction.objects.count() == 2  # only the seeded ones


def test_idempotency_key_replays_instead_of_charging_twice(client):
    key = str(uuid.uuid4())
    data = {"card_bin": "416300", "amount": "25.00"}
    first = client.pay("/api/billing/top-up/card/", data, key=key)
    second = client.pay("/api/billing/top-up/card/", data, key=key)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert client.get("/api/billing/balance/").json()["balance"] == "41.21"


def test_idempotency_key_cannot_be_reused_on_another_endpoint(client):
    key = str(uuid.uuid4())
    client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "25.00"}, key=key)
    response = client.pay("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"}, key=key)
    assert response.status_code == 400
    assert client.get("/api/billing/balance/").json()["balance"] == "41.21"


def test_failed_charge_is_not_cached_under_the_key(client):
    """A 402 moved no money, so the same key works once the balance is there."""
    key = str(uuid.uuid4())
    pack = {"pack_id": "hv-50gb"}  # 25.00 against a 16.21 balance
    assert client.pay("/api/packs/internet/purchase/", pack, key=key).status_code == 402
    client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "20.00"})
    assert client.pay("/api/packs/internet/purchase/", pack, key=key).status_code == 201


def test_schema_and_swagger_are_served(client):
    schema = client.get("/api/schema/")
    assert schema.status_code == 200
    assert b"/api/billing/balance/" in schema.content
    assert client.get("/api/swagger/").status_code == 200
