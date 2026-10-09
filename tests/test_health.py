from unittest import mock

import pytest
from django.db.utils import OperationalError

CLOSED_PORT = "redis://127.0.0.1:1/0"  # nothing listens on port 1


def test_liveness_checks_nothing(anon, settings):
    """It answers even when every dependency is broken."""
    settings.REDIS_URL = settings.CELERY_BROKER_URL = CLOSED_PORT
    with mock.patch("api.common.health.components") as components:
        response = anon.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    components.assert_not_called()


def test_readiness_reports_every_component(anon, settings):
    settings.REDIS_URL = settings.CELERY_BROKER_URL = ""
    response = anon.get("/api/health/ready/")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "components": {
            "database": "ok",
            "redis": "not_configured",
            "broker": "not_configured",
        },
    }


def test_readiness_is_503_when_redis_is_unreachable(anon, settings):
    settings.REDIS_URL = CLOSED_PORT
    settings.CELERY_BROKER_URL = ""
    response = anon.get("/api/health/ready/")
    assert response.status_code == 503
    assert response.json() == {
        "status": "failed",
        "components": {"database": "ok", "redis": "failed", "broker": "not_configured"},
    }


def test_readiness_is_503_when_the_broker_is_unreachable(anon, settings):
    settings.REDIS_URL = ""
    settings.CELERY_BROKER_URL = CLOSED_PORT
    response = anon.get("/api/health/ready/")
    assert response.status_code == 503
    assert response.json()["components"] == {
        "database": "ok",
        "redis": "not_configured",
        "broker": "failed",
    }


def test_readiness_is_503_when_the_database_is_unreachable(anon, settings):
    settings.REDIS_URL = settings.CELERY_BROKER_URL = ""
    with mock.patch("api.common.health.connection") as connection:
        connection.cursor.side_effect = OperationalError("connection refused")
        response = anon.get("/api/health/ready/")
    assert response.status_code == 503
    assert response.json()["status"] == "failed"
    assert response.json()["components"]["database"] == "failed"


@pytest.mark.redis
def test_readiness_with_a_real_redis(anon, settings):
    if not settings.TEST_REDIS_URL:
        pytest.skip("needs Redis (set REDIS_URL)")
    settings.REDIS_URL = settings.CELERY_BROKER_URL = settings.TEST_REDIS_URL
    response = anon.get("/api/health/ready/")
    assert response.status_code == 200
    assert response.json()["components"] == {"database": "ok", "redis": "ok", "broker": "ok"}


@pytest.mark.parametrize("path", ["/api/health/", "/api/health/ready/"])
def test_probes_need_no_credentials_and_are_never_cached(anon, settings, path):
    settings.REDIS_URL = settings.CELERY_BROKER_URL = ""
    response = anon.get(path)
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    # a broken Authorization header is ignored, not rejected
    assert anon.get(path, HTTP_AUTHORIZATION="Bearer broken").status_code == 200


@pytest.mark.parametrize("path", ["/api/health/", "/api/health/ready/"])
def test_probes_do_not_depend_on_the_language_header(anon, settings, path):
    settings.REDIS_URL = settings.CELERY_BROKER_URL = ""
    plain = anon.get(path)
    for language in ("az", "en", "de"):
        localized = anon.get(path, HTTP_ACCEPT_LANGUAGE=language)
        assert localized.content == plain.content
        assert "Content-Language" not in localized
        assert "Accept-Language" not in localized.get("Vary", "")


@pytest.mark.parametrize("path", ["/api/health/", "/api/health/ready/"])
def test_probes_are_not_throttled(anon, settings, path):
    settings.REDIS_URL = settings.CELERY_BROKER_URL = ""
    settings.THROTTLE_RATES = dict.fromkeys(settings.THROTTLE_RATES, "1/min")
    assert [anon.get(path).status_code for _ in range(10)] == [200] * 10


@pytest.mark.parametrize("path", ["/api/health/", "/api/health/ready/"])
def test_probes_answer_over_plain_http_when_tls_is_enforced(anon, settings, path):
    """Container healthchecks do not speak TLS; everything else is redirected."""
    settings.REDIS_URL = settings.CELERY_BROKER_URL = ""
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_REDIRECT_EXEMPT = [r"^api/health/"]
    assert anon.get(path).status_code == 200
    assert anon.get("/api/users/me/").status_code == 301


def test_swagger_ui_renders_without_credentials(anon):
    response = anon.get("/api/swagger/")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")


def test_unhandled_error_is_a_json_500(client):
    with mock.patch("api.billing.services.balance_of", side_effect=RuntimeError("boom")):
        response = client.get("/api/billing/balance/")
    assert response.status_code == 500
    assert response["Content-Type"].startswith("application/json")
    assert response.json()["code"] == "server_error"
