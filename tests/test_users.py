from rest_framework_simplejwt.tokens import AccessToken


def test_me_returns_the_signed_in_subscriber(client, subscriber):
    response = client.get("/api/users/me/", HTTP_X_APP_VERSION="1.4.0")
    assert response.status_code == 200
    body = response.json()
    assert body["msisdn"] == "994516643342"
    assert body["display_msisdn"] == "051 664 33 42"
    assert body["app_version"] == "Version 1.4.0"
    assert body["is_premium"] is True


def test_me_needs_a_token(anon):
    response = anon.get("/api/users/me/")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_a_bearer_token_signs_in(anon, subscriber):
    token = AccessToken.for_user(subscriber)
    response = anon.get("/api/users/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    assert response.json()["id"] == subscriber.id


def test_an_expired_token_is_told_apart(anon, subscriber):
    token = AccessToken.for_user(subscriber)
    token.set_exp(lifetime=-token.lifetime)
    response = anon.get("/api/users/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"


def test_demo_auth_acts_as_the_demo_subscriber_only_when_on(anon, subscriber, settings):
    assert anon.get("/api/users/me/").status_code == 401
    settings.DEMO_AUTH = True
    assert anon.get("/api/users/me/").json()["msisdn"] == subscriber.msisdn
    assert anon.get("/api/users/me/", HTTP_AUTHORIZATION="Bearer broken").status_code == 401


def test_sign_in_is_routed_but_not_implemented(anon):
    response = anon.post_json("/api/users/otp/send/", {"msisdn": "994516643342"})
    assert response.status_code == 501
    assert response.json()["code"] == "not_implemented"
