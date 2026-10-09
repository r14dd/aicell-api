"""Signing in with a number and the fixed test code, then using only one's own data."""

import pytest

from api.users.models import Subscriber

SEND = "/api/users/otp/send/"
VERIFY = "/api/users/otp/verify/"
REFRESH = "/api/users/token/refresh/"


def sign_in(anon, msisdn, code="000000"):
    request_id = anon.post_json(SEND, {"msisdn": msisdn}).json()["request_id"]
    return anon.post_json(VERIFY, {"request_id": request_id, "code": code})


def bearer(anon, access):
    anon.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return anon


def test_send_answers_as_documented(anon, subscriber):
    response = anon.post_json(SEND, {"msisdn": subscriber.msisdn})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"request_id", "ttl", "resend_after"}
    assert (body["ttl"], body["resend_after"]) == (300, 60)


def test_verify_returns_tokens_and_the_profile(anon, subscriber):
    response = sign_in(anon, subscriber.msisdn)
    assert response.status_code == 200
    body = response.json()
    assert body["access"] and body["refresh"]
    assert body["subscriber"]["msisdn"] == subscriber.msisdn
    assert body["subscriber"]["display_name"] == subscriber.display_name


def test_each_subscriber_sees_only_their_own_data(anon, subscriber, other):
    mine = sign_in(anon, subscriber.msisdn).json()["access"]
    theirs = sign_in(anon, other.msisdn).json()["access"]
    assert bearer(anon, mine).get("/api/users/me/").json()["msisdn"] == subscriber.msisdn
    assert bearer(anon, mine).get("/api/billing/balance/").status_code == 200
    me = bearer(anon, theirs).get("/api/users/me/").json()
    assert me["msisdn"] == other.msisdn


def test_unknown_staff_and_inactive_numbers_cannot_sign_in(anon, subscriber):
    assert anon.post_json(SEND, {"msisdn": "994509999999"}).status_code == 404
    Subscriber.objects.create_user("994509999998", is_staff=True)
    assert anon.post_json(SEND, {"msisdn": "994509999998"}).status_code == 404
    subscriber.is_active = False
    subscriber.save()
    assert anon.post_json(SEND, {"msisdn": subscriber.msisdn}).status_code == 404


def test_a_second_send_within_a_minute_is_429(anon, subscriber):
    assert anon.post_json(SEND, {"msisdn": subscriber.msisdn}).status_code == 200
    response = anon.post_json(SEND, {"msisdn": subscriber.msisdn})
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"


def test_wrong_codes_count_down_and_then_the_request_is_gone(anon, subscriber):
    request_id = anon.post_json(SEND, {"msisdn": subscriber.msisdn}).json()["request_id"]
    lefts = []
    for _ in range(5):
        response = anon.post_json(VERIFY, {"request_id": request_id, "code": "123456"})
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_code"
        lefts.append(response.json()["attempts_left"])
    assert lefts == [4, 3, 2, 1, 0]
    # the right code no longer helps
    response = anon.post_json(VERIFY, {"request_id": request_id, "code": "000000"})
    assert response.status_code == 400


def test_a_code_is_used_once(anon, subscriber):
    request_id = anon.post_json(SEND, {"msisdn": subscriber.msisdn}).json()["request_id"]
    good = {"request_id": request_id, "code": "000000"}
    assert anon.post_json(VERIFY, good).status_code == 200
    assert anon.post_json(VERIFY, good).status_code == 400


def test_the_code_follows_the_setting(anon, subscriber, settings):
    settings.OTP_TEST_CODE = "424242"
    assert sign_in(anon, subscriber.msisdn).status_code == 400


def test_refresh_gives_a_working_access_token(anon, subscriber):
    refresh = sign_in(anon, subscriber.msisdn).json()["refresh"]
    response = anon.post_json(REFRESH, {"refresh": refresh})
    assert response.status_code == 200
    access = response.json()["access"]
    assert bearer(anon, access).get("/api/users/me/").json()["msisdn"] == subscriber.msisdn


@pytest.mark.parametrize("token", ["nonsense", ""])
def test_a_bad_refresh_token_is_refused(anon, token):
    response = anon.post_json(REFRESH, {"refresh": token})
    assert response.status_code == 400
    assert response.json()["code"] in ("invalid_token", "validation_error")
