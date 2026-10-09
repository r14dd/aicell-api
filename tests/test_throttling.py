"""Request limits. They are off in the rest of the suite; each test here sets its own."""

import pytest
from django.core.cache import caches

from api.billing.models import Transaction
from config import env

CARD = {"card_bin": "416300", "amount": "1.00"}


def limits(settings, **rates):
    settings.THROTTLE_RATES = {**dict.fromkeys(settings.THROTTLE_RATES), **rates}


def test_sign_in_is_limited_per_address(anon, settings):
    limits(settings, otp_ip="3/min")
    statuses = [anon.post_json("/api/users/otp/send/").status_code for _ in range(5)]
    assert statuses == [501, 501, 501, 429, 429]
    # the limit follows the address, and is shared by both sign-in endpoints
    assert anon.post_json("/api/users/otp/verify/").status_code == 429
    assert anon.post_json("/api/users/otp/send/", REMOTE_ADDR="10.0.0.9").status_code == 501


def test_sign_in_is_limited_per_number_across_addresses(anon, settings):
    limits(settings, otp_phone="2/min")
    target = {"msisdn": "994516643342"}
    statuses = [
        anon.post_json("/api/users/otp/send/", target, REMOTE_ADDR=f"10.0.0.{index}").status_code
        for index in range(4)
    ]
    assert statuses == [501, 501, 429, 429]
    other = anon.post_json("/api/users/otp/send/", {"msisdn": "994500000002"})
    assert other.status_code == 501


def test_the_429_uses_the_shared_error_shape_and_says_when_to_retry(anon, settings):
    limits(settings, otp_ip="1/min")
    anon.post_json("/api/users/otp/send/")
    response = anon.post_json("/api/users/otp/send/")
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert set(response.json()) == {"code", "detail"}
    wait = int(response["Retry-After"])
    assert 0 < wait <= 60
    assert response.json()["detail"] == f"Too many requests, try again in {wait} seconds"


@pytest.mark.parametrize(
    "language,start",
    [("az", "Həddən çox sorğu"), ("ru", "Слишком много запросов"), ("en", "Too many requests")],
)
def test_the_429_is_in_the_requested_language(anon, settings, language, start):
    limits(settings, otp_ip="1/min")
    anon.post_json("/api/users/otp/send/")
    response = anon.post_json("/api/users/otp/send/", HTTP_ACCEPT_LANGUAGE=language)
    assert response.status_code == 429
    assert response.json()["detail"].startswith(start)
    assert response["Content-Language"] == language


def test_money_posts_are_limited_per_subscriber(client, other_client, settings):
    limits(settings, money="3/min")
    paths = [
        "/api/billing/top-up/card/",
        "/api/billing/top-up/card/",
        "/api/billing/top-up/card/",
        "/api/billing/top-up/card/",
        "/api/packs/internet/purchase/",
    ]
    statuses = [client.pay(path, CARD).status_code for path in paths]
    assert statuses == [201, 201, 201, 429, 429]  # one limit over every money endpoint

    # refused before anything happened: three top-ups, nothing else
    assert client.get("/api/billing/balance/").json()["balance"] == "19.21"
    assert Transaction.objects.filter(subscriber__msisdn="994516643342").count() == 5
    # reads are not affected, and neither is another subscriber
    assert client.get("/api/billing/transactions/").status_code == 200
    assert other_client.pay("/api/billing/top-up/card/", CARD).status_code == 201


def test_everything_else_shares_a_wide_limit_per_subscriber(client, other_client, settings):
    limits(settings, subscriber="5/min")
    paths = ["/api/users/me/", "/api/sim/", "/api/content/home/", "/api/billing/balance/"]
    statuses = [client.get(paths[index % len(paths)]).status_code for index in range(7)]
    assert statuses == [200] * 5 + [429] * 2
    assert client.post_json("/api/content/app-rating/", {"stars": 5}).status_code == 429
    assert other_client.get("/api/users/me/").status_code == 200


def test_todo_endpoints_count_towards_the_limit(client, settings):
    limits(settings, subscriber="2/min")
    statuses = [client.post_json("/api/billing/top-up/voucher/").status_code for _ in range(3)]
    assert statuses == [501, 501, 429]


def test_limits_can_be_switched_off(client, settings):
    limits(settings)  # every rate is None
    assert all(client.get("/api/users/me/").status_code == 200 for _ in range(40))


def test_rates_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("THROTTLE_MONEY", "7/hour")
    assert env.rate("THROTTLE_MONEY", "30/min") == "7/hour"
    monkeypatch.setenv("THROTTLE_MONEY", "")
    assert env.rate("THROTTLE_MONEY", "30/min") is None  # empty switches it off
    monkeypatch.delenv("THROTTLE_MONEY")
    assert env.rate("THROTTLE_MONEY", "30/min") == "30/min"


def test_default_rates(settings):
    from config import settings as configured

    assert set(configured.THROTTLE_RATES) == {"otp_ip", "otp_phone", "money", "subscriber"}


@pytest.mark.redis
def test_limits_are_counted_in_redis(anon, settings):
    """With Redis as the cache, the counter lives there and is shared by every worker."""
    if not settings.TEST_REDIS_URL:
        pytest.skip("needs Redis (set REDIS_URL)")
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": settings.TEST_REDIS_URL,
            "KEY_PREFIX": "aicell-test",
        }
    }
    caches["default"].clear()
    limits(settings, otp_ip="2/min")
    try:
        statuses = [anon.post_json("/api/users/otp/send/").status_code for _ in range(3)]
        assert statuses == [501, 501, 429]

        import redis

        keys = redis.Redis.from_url(settings.TEST_REDIS_URL).keys("aicell-test:*otp_ip*")
        assert len(keys) == 1
    finally:
        caches["default"].clear()
