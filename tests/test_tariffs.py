from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from api.tariffs.models import PriceGroup, SubscriberTariff, TariffFamily, TariffPlan


@pytest.fixture
def catalogue(db):
    family = TariffFamily.objects.create(slug="digimax", name="DigiMax", badges=["PREPAID"])
    TariffPlan.objects.create(
        family=family, slug="digimax-25", title="DigiMax 25", price=Decimal("25"), is_default=True
    )
    TariffPlan.objects.create(
        family=family,
        slug="digimax-40",
        title="DigiMax 40",
        price=Decimal("40"),
        hot_position=1,
        order=1,
    )
    PriceGroup.objects.create(heading="Calls", rows=[{"label": "Local", "price": "0.05"}])
    TariffFamily.objects.create(slug="hidden", name="Hidden", is_active=False)


@pytest.fixture
def my_tariff(subscriber):
    now = timezone.now()
    return SubscriberTariff.objects.create(
        subscriber=subscriber,
        activated_at=now - timedelta(days=5),
        last_payment_at=now - timedelta(days=5),
        next_payment_at=now + timedelta(days=25),
    )


def test_catalogue_lists_active_families_with_the_default_plan(client, catalogue):
    body = client.get("/api/tariffs/catalogue/").json()
    assert [family["id"] for family in body["results"]] == ["digimax"]
    family = body["results"][0]
    assert family["selected_plan"] == "digimax-25"
    assert [plan["price"] for plan in family["plans"]] == ["25.00", "40.00"]
    assert family["cta"] == "Subscribe for 25.00 ₼"
    assert family["total_price"][0]["heading"] == "Calls"


def test_a_family_page_selects_the_asked_plan(client, catalogue):
    body = client.get("/api/tariffs/catalogue/digimax/?plan=digimax-40").json()
    assert body["selected_plan"] == "digimax-40"
    assert client.get("/api/tariffs/catalogue/digimax/?plan=nope").status_code == 400
    assert client.get("/api/tariffs/catalogue/hidden/").status_code == 404


def test_hot_shelf_only_holds_plans_with_a_position(client, catalogue):
    body = client.get("/api/tariffs/hot/").json()
    assert [card["id"] for card in body["results"]] == ["digimax-40"]


def test_editing_the_catalogue_drops_the_cached_answer(client, catalogue):
    assert client.get("/api/tariffs/hot/").json()["results"]
    TariffPlan.objects.update(hot_position=None)
    TariffPlan.objects.first().save()  # a save bumps the catalogue version
    assert client.get("/api/tariffs/hot/").json()["results"] == []


def test_my_tariff_and_usage(client, my_tariff):
    mine = client.get("/api/tariffs/my/").json()
    assert mine["title"] == "IsteSen"
    assert [row["kind"] for row in mine["usage"]] == ["internet", "messaging", "calls"]
    assert mine["pills"][0] == "CURRENT TARIFF"
    usage = client.get("/api/tariffs/my/usage/").json()
    assert usage["period_left"]["days"] == 24
    assert usage["remaining"]["minutes"] == 30


def test_redesign_estimate_follows_the_sliders(client, my_tariff):
    my_tariff.redesign = {"internet": 20, "calls": 30, "instagramFb": 0, "youtube": 0, "tiktok": 0}
    my_tariff.save()
    assert client.get("/api/tariffs/my/redesign/").json()["estimate"] == "21.10"


def test_my_tariff_is_404_without_one(client):
    assert client.get("/api/tariffs/my/").status_code == 404


def test_todo_routes_answer_501(client):
    assert client.post_json("/api/tariffs/subscribe/").status_code == 501
