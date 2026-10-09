from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from api.billing import services as billing
from api.packs import services
from api.packs.models import (
    InternetPack,
    PackActivation,
    PackCategory,
    RoamingPack,
    SocialPack,
    SocialPlan,
)


@pytest.fixture
def packs(db):
    category = PackCategory.objects.create(slug="daily", label="Daily")
    InternetPack.objects.create(
        category=category,
        slug="unlimited-1h",
        name="Unlimited",
        sub="1 hour",
        label="Unlimited 1h",
        price=Decimal("0.99"),
        hours=1,
        top_position=1,
    )
    InternetPack.objects.create(
        category=category,
        slug="big",
        name="Big",
        sub="30 GB",
        label="Big 30 GB",
        price=Decimal("30"),
        hours=720,
    )
    tehsil = SocialPack.objects.create(
        slug="tehsil",
        title="Tehsil",
        subtitle="Study",
        app="tehsil",
        price_range="1-5",
        volume="100 GB",
        cta="Activate",
        auto_renew=True,
    )
    SocialPlan.objects.create(
        pack=tehsil, slug="100gb", title="100 GB", price=3, validity="7 days", days=7
    )
    RoamingPack.objects.create(slug="r-500mb", name="500 MB", sub="7 days", price=5, days=7)


@pytest.fixture
def funded(subscriber):
    billing.top_up(subscriber, "card", Decimal("10.00"))
    return subscriber


def test_internet_page_groups_packs_by_category(client, packs):
    body = client.get("/api/packs/internet/").json()
    assert [category["id"] for category in body["categories"]] == ["daily"]
    assert [pack["id"] for pack in body["packs"]["daily"]] == ["unlimited-1h", "big"]
    assert body["social"][0]["id"] == "tehsil" and "plans" not in body["social"][0]
    assert body["msisdn"] == "994516643342"
    assert [pack["id"] for pack in client.get("/api/packs/internet/top/").json()["results"]] == [
        "unlimited-1h"
    ]


def test_buying_a_pack_charges_the_wallet_and_activates_it(client, packs, funded):
    response = client.pay("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"})
    assert response.status_code == 201
    body = response.json()
    assert body["balance"] == "9.01"
    assert body["transaction"]["amount"] == "-0.99"
    assert body["activation"]["status"] == "active"
    assert PackActivation.objects.filter(subscriber=funded, kind="internet").count() == 1


def test_a_pack_that_costs_too_much_changes_nothing(client, packs, funded):
    response = client.pay("/api/packs/internet/purchase/", {"pack_id": "big"})
    assert response.status_code == 402
    assert response.json()["code"] == "insufficient_balance"
    assert billing.balance_of(funded) == Decimal("10.00")
    assert not PackActivation.objects.exists()


def test_unknown_pack_is_a_validation_error(client, packs, funded):
    assert client.pay("/api/packs/internet/purchase/", {"pack_id": "nope"}).status_code == 400
    assert client.pay("/api/packs/internet/purchase/", {}).status_code == 400


def test_auto_renewing_social_pack_activates_once(client, packs, funded):
    body = client.get("/api/packs/social/tehsil/").json()
    assert body["default_plan"] == "100gb" and body["badge"] == "AUTO-RENEWAL"
    assert client.get("/api/packs/social/nope/").status_code == 404

    first = client.pay("/api/packs/social/tehsil/activate/", {"plan_id": "100gb"})
    assert first.status_code == 201
    again = client.pay("/api/packs/social/tehsil/activate/", {"plan_id": "100gb"})
    assert again.status_code == 409 and again.json()["code"] == "already_active"
    assert billing.balance_of(funded) == Decimal("7.00")


def test_roaming_purchase(client, packs, funded):
    assert client.get("/api/packs/roaming/").json()["results"][0]["id"] == "r-500mb"
    response = client.pay("/api/packs/roaming/purchase/", {"pack_id": "r-500mb"})
    assert response.status_code == 201
    assert response.json()["activation"]["label"] == "Roaming 500 MB"


def test_expired_activations_are_switched_off(packs, funded):
    services.purchase_internet(funded, "unlimited-1h")
    PackActivation.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    assert services.expire_activations() == 1
    assert PackActivation.objects.get().status == "expired"
    assert services.expire_activations() == 0
