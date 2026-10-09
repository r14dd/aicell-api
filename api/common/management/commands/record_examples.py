"""Record a real answer of every ready endpoint into `api/common/examples.json`.

Swagger's response schemas and examples are built from these recordings, so
they cannot describe a shape the server does not actually return. Run it after
changing what an endpoint answers:

    manage.py record_examples

Everything happens inside one database transaction that is rolled back: the
command seeds its own data, calls the API as the demo subscriber and leaves
the database exactly as it found it.
"""

import json
import re
import uuid
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import override_settings
from django.urls import get_resolver
from rest_framework.test import APIClient

from api.billing.models import Wallet
from api.common import schema
from api.common.routing import Todo
from api.seeding import seed_catalogue, seed_demo

# Handlers the demo subscriber cannot afford with its seeded balance: their
# example is recorded with this much in the wallet (and undone like any write).
FUNDED = {"renew": "50.00"}


def _sign_in_body(subscriber):
    from api.users import services

    return {"request_id": services.start(subscriber.msisdn), "code": "000000"}


def _refresh_body(subscriber):
    from rest_framework_simplejwt.tokens import RefreshToken

    return {"refresh": str(RefreshToken.for_user(subscriber))}


# Handlers whose input only exists at run time: a function of the subscriber gives it.
BODIES = {"otp_verify_post": _sign_in_body, "token_refresh_post": _refresh_body}
PARAMETER = re.compile(r"<(?:\w+:)?(\w+)>")


def routes(resolver=None, prefix=""):
    """Every `(path template, view class)` under the URL configuration."""
    for pattern in (resolver or get_resolver()).url_patterns:
        path = prefix + str(pattern.pattern)
        if hasattr(pattern, "url_patterns"):
            yield from routes(pattern, path)
        elif hasattr(getattr(pattern.callback, "cls", None), "handlers"):
            yield path, pattern.callback.cls


def _fill(template: str, samples: dict) -> str:
    """`sim/services/<slug:slug>/` with `{"slug": "missed-call"}` -> a real path."""
    return "/" + PARAMETER.sub(lambda match: str(samples[match[1]]), template)


def ready_endpoints():
    """`(method, path, handler)` of every implemented endpoint, reads first."""
    found = []
    for template, view in routes():
        for method, handler in view.handlers.items():
            if isinstance(handler, Todo):
                continue
            found.append((method, _fill(template, handler.doc.path), handler))
    return sorted(found, key=lambda item: item[0] != "get")


def _upload(client, path, headers):
    """An endpoint that takes a recording: Gemini is faked, so recording needs no key or network."""
    from api.assistant import gemini

    audio = SimpleUploadedFile("question.wav", b"RIFF", content_type="audio/wav")
    with (
        mock.patch.object(gemini, "transcribe", return_value="How much internet do I have left?"),
        mock.patch.object(gemini, "speak", return_value=b"RIFF"),
    ):
        return client.post(path, {"audio": audio}, format="multipart", **headers)


def call(client, method, path, handler):
    """Call an endpoint with its sample input. A write is undone afterwards.

    Undoing writes means each one is answered from the same seeded state, so
    an example does not depend on which endpoints were called before it (an
    offer can be accepted in one example and declined in the next).
    Must run inside a transaction.
    """
    headers = {"HTTP_ACCEPT": "application/json"}
    if getattr(handler, "idempotent", False):
        headers["HTTP_IDEMPOTENCY_KEY"] = str(uuid.uuid4())
    savepoint = None if method == "get" else transaction.savepoint()
    if savepoint and handler.__name__ in FUNDED:
        subscriber = client.handler._force_user
        Wallet.objects.filter(subscriber=subscriber).update(balance=FUNDED[handler.__name__])
    body = handler.doc.example or {}
    if handler.__name__ in BODIES:
        body = BODIES[handler.__name__](client.handler._force_user)
    try:
        if getattr(handler, "upload", False):
            return _upload(client, path, headers)
        return client.generic(
            method.upper(),
            path,
            json.dumps(body),
            content_type="application/json",
            **headers,
        )
    finally:
        if savepoint:
            transaction.savepoint_rollback(savepoint)


def record() -> dict:
    subscriber, _created = seed_demo(reset=True)
    client = APIClient(SERVER_NAME="localhost")
    client.force_authenticate(user=subscriber)
    recorded = {}
    for method, path, handler in ready_endpoints():
        response = call(client, method, path, handler)
        if response.status_code != handler.doc.status and not handler.doc.streams:
            raise RuntimeError(f"{method.upper()} {path} answered {response.status_code}")
        recorded[schema.example_key(method, handler)] = response.json()
    return recorded


class Command(BaseCommand):
    help = "Record the answers Swagger's response schemas and examples are built from."

    @override_settings(
        ALLOWED_HOSTS=["*"],
        THROTTLE_RATES={},
        ASSISTANT_STREAM_DELAY=0,
        GOOGLE_PAY_SIMULATED=True,
        LAYA_BRAIN="api.laya.offline",
        SECURE_SSL_REDIRECT=False,
        # Sign-in requests live in the cache; keep them out of a real Redis.
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    )
    def handle(self, *args, **options):
        with transaction.atomic():
            seed_catalogue()
            recorded = record()
            transaction.set_rollback(True)
        schema.EXAMPLES_FILE.write_text(
            json.dumps(recorded, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        self.stdout.write(self.style.SUCCESS(f"Recorded {len(recorded)} answers"))
