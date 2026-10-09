import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _test_settings(settings):
    settings.THROTTLE_RATES = dict.fromkeys(settings.THROTTLE_RATES)  # all off


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


class Client(APIClient):
    """JSON client with shorthands for the request kinds the API has."""

    def post_json(self, path, data=None, **extra):
        return self.post(path, data or {}, format="json", **extra)

    def patch_json(self, path, data=None, **extra):
        return self.patch(path, data or {}, format="json", **extra)


@pytest.fixture
def anon(db):
    """No credentials at all."""
    return Client(raise_request_exception=False)


def client_for(user) -> Client:
    client = Client(raise_request_exception=False)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def subscriber(db):
    from api.users.models import Subscriber

    return Subscriber.objects.create_user(
        "994516643342", display_name="Demo Subscriber", is_premium=True
    )


@pytest.fixture
def client(subscriber):
    """Signed in as the demo subscriber."""
    return client_for(subscriber)
