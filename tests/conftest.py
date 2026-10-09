import uuid

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from api.seeding import Profile, seed_catalogue, seed_demo, seed_subscriber

OTHER_MSISDN = "994500000002"
OTHER_CONVERSATION_ID = 4000001
OTHER_OFFER_ID = 9500
OTHER_INSIGHT_ID = 7500
OTHER = Profile(
    display_name="Other Person",
    balance="99.99",
    card_last4="9999",
    steam_account="other_steam",
    referral_code="zz99ZZ",
    puk1="11112222",
    puk2="33334444",
    conversation_id=OTHER_CONVERSATION_ID,
    offer_id=OTHER_OFFER_ID,
    insight_id=OTHER_INSIGHT_ID,
)


@pytest.fixture(autouse=True)
def _test_settings(settings):
    settings.DEMO_AUTH = False
    settings.GOOGLE_PAY_SIMULATED = True
    settings.ASSISTANT_STREAM_DELAY = 0
    settings.THROTTLE_RATES = dict.fromkeys(settings.THROTTLE_RATES)  # all off
    settings.INSIGHTS_QUIET_HOURS = None  # tests run at any hour


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def catalogue(db):
    seed_catalogue()


@pytest.fixture
def subscriber(catalogue):
    return seed_demo()[0]


@pytest.fixture
def other(subscriber):
    """A second subscriber whose data must never leak into the first one's answers."""
    return seed_subscriber(OTHER_MSISDN, OTHER)


class Client(APIClient):
    """JSON client with shorthands for the request kinds the API has."""

    def post_json(self, path, data=None, **extra):
        return self.post(path, data or {}, format="json", **extra)

    def patch_json(self, path, data=None, **extra):
        return self.patch(path, data or {}, format="json", **extra)

    def pay(self, path, data=None, key=None):
        """POST that moves money: sends an Idempotency-Key."""
        return self.post_json(path, data, HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def client_for(user) -> Client:
    client = Client(raise_request_exception=False)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def client(subscriber):
    """Signed in as the demo subscriber."""
    return client_for(subscriber)


@pytest.fixture
def other_client(other):
    return client_for(other)


@pytest.fixture
def anon(db):
    """No credentials at all."""
    return Client(raise_request_exception=False)
