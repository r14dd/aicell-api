"""Liveness and readiness probes.

Both are open, never cached, never throttled and answer the same whatever
headers a request carries: they are for load balancers, not for the app.
"""

from django.conf import settings
from django.db import connection
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

TIMEOUT_SECONDS = 2

OK, FAILED, NOT_CONFIGURED = "ok", "failed", "not_configured"

ComponentsSerializer = inline_serializer(
    "HealthComponents",
    {
        "database": serializers.CharField(help_text="`ok` or `failed`"),
        "redis": serializers.CharField(help_text="`ok`, `failed` or `not_configured`"),
        "broker": serializers.CharField(help_text="`ok`, `failed` or `not_configured`"),
    },
)
ReadySerializer = inline_serializer(
    "HealthReady",
    {
        "status": serializers.CharField(help_text="`ok` or `failed`"),
        "components": ComponentsSerializer,
    },
)


def _database() -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return OK
    except Exception:
        return FAILED


def _redis(url: str) -> str:
    """Ping a Redis URL; used for both the cache and the Celery broker."""
    if not url:
        return NOT_CONFIGURED
    if not url.startswith(("redis://", "rediss://")):
        return NOT_CONFIGURED  # another kind of broker: not ours to probe
    import redis

    try:
        client = redis.Redis.from_url(
            url, socket_connect_timeout=TIMEOUT_SECONDS, socket_timeout=TIMEOUT_SECONDS
        )
        try:
            client.ping()
        finally:
            client.close()
        return OK
    except Exception:
        return FAILED


def components() -> dict[str, str]:
    return {
        "database": _database(),
        "redis": _redis(settings.REDIS_URL),
        "broker": _redis(settings.CELERY_BROKER_URL),
    }


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class LiveView(HealthView):
    @extend_schema(
        tags=["health"],
        summary="Liveness",
        description="The process is up. Checks nothing else, so it stays fast and "
        "never fails because of a dependency.",
        operation_id="health_live",
        auth=[],
        responses={200: inline_serializer("HealthLive", {"status": serializers.CharField()})},
        examples=[OpenApiExample("Up", value={"status": "ok"})],
    )
    def get(self, request):
        return Response({"status": OK})


class ReadyView(HealthView):
    @extend_schema(
        tags=["health"],
        summary="Readiness",
        description="Checks the database, Redis and the Celery broker and reports each. "
        "`503` when one of them fails. A component without configuration "
        "(a local run without Redis) is `not_configured` and does not fail the probe.",
        operation_id="health_ready",
        auth=[],
        responses={200: ReadySerializer, 503: ReadySerializer},
        examples=[
            OpenApiExample(
                "Ready",
                value={
                    "status": "ok",
                    "components": {"database": "ok", "redis": "ok", "broker": "ok"},
                },
                status_codes=[200],
            ),
            OpenApiExample(
                "Redis down",
                value={
                    "status": "failed",
                    "components": {"database": "ok", "redis": "failed", "broker": "failed"},
                },
                status_codes=[503],
            ),
        ],
    )
    def get(self, request):
        states = components()
        healthy = FAILED not in states.values()
        return Response(
            {"status": OK if healthy else FAILED, "components": states},
            status=200 if healthy else 503,
        )
