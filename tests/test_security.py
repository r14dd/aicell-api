"""Settings that decide how safe a deployment is, checked the way they are used:
by starting Django with a given environment.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SECRET = "a-long-random-secret-key-used-only-inside-this-test-run-0123456789"

SETTINGS = [
    "DEBUG", "ALLOWED_HOSTS", "CORS_ALLOW_ALL_ORIGINS", "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS", "DEMO_AUTH", "SECURE_CONTENT_TYPE_NOSNIFF",
]  # fmt: skip
PRODUCTION_ONLY = [
    "SECURE_SSL_REDIRECT", "SECURE_HSTS_SECONDS", "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "SECURE_PROXY_SSL_HEADER", "SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE",
]  # fmt: skip


def django(*args, **environment):
    """Run a fresh Python with only the given configuration."""
    base = {"PATH": os.environ["PATH"], "DJANGO_READ_DOT_ENV": "false"}
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env={**base, **environment},
        capture_output=True,
        text=True,
        timeout=120,
    )


def settings(**environment) -> dict:
    code = (
        "import json, django; from django.conf import settings; django.setup();"
        f"names = {SETTINGS + PRODUCTION_ONLY!r};"
        "print(json.dumps({n: getattr(settings, n, None) for n in names}))"
    )
    result = django("-c", code, DJANGO_SETTINGS_MODULE="config.settings", **environment)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_the_server_refuses_to_start_without_a_secret_key():
    result = django("manage.py", "check")
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set" in result.stderr

    explicit = django("manage.py", "check", DJANGO_DEBUG="false", DJANGO_SECRET_KEY="")
    assert explicit.returncode != 0


def test_debug_is_off_unless_asked_for():
    assert settings(DJANGO_SECRET_KEY=SECRET)["DEBUG"] is False
    assert settings(DJANGO_DEBUG="true")["DEBUG"] is True  # and then a key is not required


def test_production_defaults_are_strict():
    values = settings(DJANGO_SECRET_KEY=SECRET, DJANGO_ALLOWED_HOSTS="api.example.com")
    assert values == {
        "DEBUG": False,
        "ALLOWED_HOSTS": ["api.example.com"],
        "CORS_ALLOW_ALL_ORIGINS": False,
        "CORS_ALLOWED_ORIGINS": [],
        "CSRF_TRUSTED_ORIGINS": [],
        "DEMO_AUTH": True,
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 31536000,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
        "SECURE_PROXY_SSL_HEADER": ["HTTP_X_FORWARDED_PROTO", "https"],
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
    }


def test_no_host_is_allowed_until_one_is_configured():
    assert settings(DJANGO_SECRET_KEY=SECRET)["ALLOWED_HOSTS"] == []


def test_origins_come_from_the_environment():
    values = settings(
        DJANGO_SECRET_KEY=SECRET,
        CORS_ALLOWED_ORIGINS="https://app.example.com, https://admin.example.com",
        CSRF_TRUSTED_ORIGINS="https://admin.example.com",
    )
    assert values["CORS_ALLOWED_ORIGINS"] == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert values["CSRF_TRUSTED_ORIGINS"] == ["https://admin.example.com"]
    assert values["CORS_ALLOW_ALL_ORIGINS"] is False


def test_every_origin_is_allowed_only_in_debug():
    assert settings(DJANGO_DEBUG="true")["CORS_ALLOW_ALL_ORIGINS"] is True
    assert settings(DJANGO_SECRET_KEY=SECRET)["CORS_ALLOW_ALL_ORIGINS"] is False


@pytest.mark.parametrize("debug", ["true", "false"])
def test_demo_auth_does_not_follow_debug(debug):
    """It is its own switch, on by default in every mode."""
    base = {"DJANGO_DEBUG": debug, "DJANGO_SECRET_KEY": SECRET}
    assert settings(**base)["DEMO_AUTH"] is True
    assert settings(**base, DEMO_AUTH="false")["DEMO_AUTH"] is False


def test_deploy_check_passes_without_warnings():
    result = django(
        "manage.py", "check", "--deploy", "--fail-level", "WARNING",
        DJANGO_SECRET_KEY=SECRET, DJANGO_ALLOWED_HOSTS="api.example.com",
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no issues" in result.stdout


def test_the_local_compose_setup_trades_only_tls_checks():
    """Plain HTTP on localhost: the three TLS warnings, listed in the README, and no others."""
    result = django(
        "manage.py", "check", "--deploy",
        DJANGO_SECRET_KEY=SECRET, DJANGO_ALLOWED_HOSTS="localhost",
        SECURE_SSL_REDIRECT="false", SECURE_COOKIES="false",
    )  # fmt: skip
    warnings = sorted({part.split(")")[0] for part in result.stderr.split("(security.")[1:]})
    assert warnings == ["W008", "W012", "W016"]


def test_responses_carry_the_hardening_headers(client):
    response = client.get("/api/users/me/")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Referrer-Policy"] == "same-origin"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"


def test_hsts_is_sent_over_https(client, settings):
    settings.SECURE_HSTS_SECONDS = 31536000
    response = client.get("/api/users/me/", secure=True)
    assert response["Strict-Transport-Security"].startswith("max-age=31536000")


def test_cors_answers_only_listed_origins(client, settings):
    settings.CORS_ALLOW_ALL_ORIGINS = False
    settings.CORS_ALLOWED_ORIGINS = ["https://app.example.com"]
    listed = client.get("/api/users/me/", HTTP_ORIGIN="https://app.example.com")
    other = client.get("/api/users/me/", HTTP_ORIGIN="https://evil.example.com")
    assert listed["Access-Control-Allow-Origin"] == "https://app.example.com"
    assert "Access-Control-Allow-Origin" not in other


def test_cors_lets_the_api_headers_through(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["https://app.example.com"]
    preflight = client.options(
        "/api/billing/top-up/card/",
        HTTP_ORIGIN="https://app.example.com",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="idempotency-key,accept-language,authorization",
    )
    allowed = preflight["Access-Control-Allow-Headers"].lower()
    assert all(name in allowed for name in ("idempotency-key", "accept-language", "authorization"))


# Read by the settings but not meant to be set per deployment: switches for
# tests and local runs, and values the compose file fixes itself.
NOT_FOR_COMPOSE = {
    "ASSISTANT_RESPONDER",
    "ASSISTANT_STREAM_DELAY",
    "CATALOGUE_CACHE_SECONDS",
    "CELERY_BROKER_URL",
    "DEMO_MSISDN",
    "DJANGO_READ_DOT_ENV",
    "IDEMPOTENCY_KEY_DAYS",
    "LAYA_BRAIN",
}


def test_compose_passes_every_setting_a_deployment_may_change():
    """A variable the settings read but compose does not pass cannot be set from `.env`
    in Docker: the containers only see what `docker-compose.yml` lists."""
    import re

    read = set(
        re.findall(r'env\.\w+\(\s*"([A-Z_]+)"', (ROOT / "config" / "settings.py").read_text())
    )
    compose = (ROOT / "docker-compose.yml").read_text()
    passed = set(re.findall(r"^    ([A-Z_]+):", compose, flags=re.M))
    assert read - passed - NOT_FOR_COMPOSE == set()
    assert "ANTHROPIC_API_KEY" in passed  # without it Laya can never reach its model
