"""The catalogue lives in the database: editable, seeded idempotently, cached."""

from decimal import Decimal

import pytest
from django.apps import apps
from django.db import connection
from django.test.utils import CaptureQueriesContext

from api.common.models import CatalogueItem
from api.content.models import Banner, Story
from api.packs.models import InternetPack, RoamingPack
from api.packs.services import expire_activations
from api.seeding import seed_catalogue
from api.tariffs.models import TariffPlan

CATALOGUE_MODELS = [model for model in apps.get_models() if issubclass(model, CatalogueItem)]


def counts():
    return {model.__name__: model.objects.count() for model in CATALOGUE_MODELS}


def test_every_catalogue_model_is_seeded(catalogue):
    assert len(CATALOGUE_MODELS) == 24
    empty = [name for name, count in counts().items() if count == 0]
    assert not empty


def test_seeding_twice_changes_nothing(catalogue):
    before = counts()
    seed_catalogue()
    assert counts() == before


def test_seeding_again_keeps_what_editors_changed(catalogue):
    """The seed runs on every container start; it must not undo work done in the admin."""
    RoamingPack.objects.create(
        slug="r-custom", name="Custom", sub="1 day", price=Decimal("1.00"), days=1, order=99
    )
    RoamingPack.objects.filter(slug="r-2gb").update(price=Decimal("99.00"), name_az="Dəyişdi")
    RoamingPack.objects.filter(slug="r-5gb").delete()

    seed_catalogue()

    edited = RoamingPack.objects.get(slug="r-2gb")
    assert (edited.price, edited.name_az) == (Decimal("99.00"), "Dəyişdi")
    assert RoamingPack.objects.filter(slug="r-custom").exists()
    assert RoamingPack.objects.filter(slug="r-5gb").exists()  # a missing seeded row comes back


def test_refresh_resets_seeded_rows_and_keeps_added_ones(catalogue):
    RoamingPack.objects.create(
        slug="r-custom", name="Custom", sub="1 day", price=Decimal("1.00"), days=1, order=99
    )
    RoamingPack.objects.filter(slug="r-2gb").update(price=Decimal("99.00"))
    seed_catalogue(refresh=True)
    assert RoamingPack.objects.get(slug="r-2gb").price == Decimal("25.00")
    assert RoamingPack.objects.filter(slug="r-custom").exists()


# --- edits reach the API ----------------------------------------------------


def test_a_price_change_reaches_the_api_and_the_purchase(client):
    assert client.get("/api/packs/internet/").json()["packs"]["unlimited"][0]["price"] == "0.99"

    pack = InternetPack.objects.get(slug="unlimited-1h")
    pack.price = Decimal("1.49")
    pack.save()

    assert client.get("/api/packs/internet/").json()["packs"]["unlimited"][0]["price"] == "1.49"
    bought = client.pay("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"}).json()
    assert bought["transaction"]["amount"] == "-1.49"
    assert bought["balance"] == "14.72"


def test_a_deactivated_item_disappears_and_cannot_be_bought(client):
    RoamingPack.objects.filter(slug="r-500mb").update(is_active=False)
    RoamingPack.objects.get(slug="r-2gb").save()  # any save drops the cache
    ids = [pack["id"] for pack in client.get("/api/packs/roaming/").json()["results"]]
    assert ids == ["r-2gb", "r-5gb"]
    assert client.pay("/api/packs/roaming/purchase/", {"pack_id": "r-500mb"}).status_code == 400


def test_order_is_editable(client):
    first = Story.objects.get(key="gift-wheel")
    first.order = 50
    first.save()
    keys = [chip["key"] for chip in client.get("/api/content/stories/").json()["results"]]
    assert keys[0] == "roaming" and keys[-1] == "gift-wheel"
    assert client.get("/api/content/stories/gift-wheel/").json()["next_key"] is None


def test_a_translation_is_editable_per_language(client):
    plan = TariffPlan.objects.get(slug="digimax-5")
    plan.title_ru = "ДиджиМакс 5ГБ"
    plan.save()
    path = "/api/tariffs/catalogue/digimax/"
    assert (
        client.get(path, HTTP_ACCEPT_LANGUAGE="ru").json()["plans"][0]["title"] == "ДиджиМакс 5ГБ"
    )
    assert client.get(path, HTTP_ACCEPT_LANGUAGE="en").json()["plans"][0]["title"] == "DigiMax 5GB"


def test_a_new_row_appears_without_code_changes(client):
    Banner.objects.create(
        placement="partners", key="new-partner", image="banner-new.png", alt="New", order=9
    )
    keys = [
        b["key"] for b in client.get("/api/content/banners/?placement=partners").json()["results"]
    ]
    assert keys == ["wingz", "wolt", "new-partner"]


def test_deleting_a_row_drops_the_cache(client):
    assert len(client.get("/api/content/perks/").json()["results"]) == 2
    from api.content.models import Offer

    Offer.objects.get(kind="perk", slug="wingz").delete()
    assert [perk["id"] for perk in client.get("/api/content/perks/").json()["results"]] == [
        "wolt-plus"
    ]


# --- cache ------------------------------------------------------------------


# Quoted, so that `content_story` does not also match `content_storyview`.
CATALOGUE_TABLES = tuple(f'"{model._meta.db_table}"' for model in CATALOGUE_MODELS)


def catalogue_queries(client, path, **headers):
    with CaptureQueriesContext(connection) as queries:
        assert client.get(path, **headers).status_code == 200
    return [q["sql"] for q in queries if any(table in q["sql"] for table in CATALOGUE_TABLES)]


@pytest.mark.parametrize(
    "path",
    [
        "/api/tariffs/catalogue/",
        "/api/tariffs/hot/",
        "/api/tariffs/change/",
        "/api/tariffs/premium/",
        "/api/packs/internet/",
        "/api/packs/roaming/",
        "/api/kredit/",
        "/api/sim/services/",
        "/api/content/home/",
        "/api/content/lottery/rules/",
        "/api/content/games/",
        "/api/content/offers/apps/",
        "/api/referral/me/",
    ],
)
def test_catalogue_reads_are_served_from_the_cache(client, path):
    assert catalogue_queries(client, path), "the first read builds the answer from the database"
    assert catalogue_queries(client, path) == [], "the second read touched the catalogue tables"


def test_the_cache_is_kept_per_language(client):
    path = "/api/packs/roaming/"
    assert catalogue_queries(client, path, HTTP_ACCEPT_LANGUAGE="az")
    assert catalogue_queries(client, path, HTTP_ACCEPT_LANGUAGE="ru"), "ru must not reuse az"
    assert catalogue_queries(client, path, HTTP_ACCEPT_LANGUAGE="az") == []


def test_subscriber_data_is_never_cached(client, other_client):
    """Two subscribers share the cached catalogue but never each other's state."""
    assert client.get("/api/content/home/").status_code == 200  # warms the cache
    client.post_json("/api/content/stories/gift-wheel/viewed/")
    mine = client.get("/api/content/home/").json()["stories"]
    theirs = other_client.get("/api/content/home/").json()["stories"]
    assert mine[-1] == {**mine[-1], "key": "gift-wheel", "viewed": True}
    assert not any(chip["viewed"] for chip in theirs)

    client.pay("/api/sim/services/missed-call/subscribe/", {})
    mine = client.get("/api/sim/services/").json()["results"][0]
    theirs = other_client.get("/api/sim/services/").json()["results"][0]
    assert (mine["activated"], theirs["activated"]) == (True, False)


def test_cached_answers_do_not_carry_the_host_of_the_first_request(client):
    first = client.get("/api/content/home/", HTTP_HOST="localhost").json()
    second = client.get("/api/content/home/", HTTP_HOST="testserver").json()
    assert first["banners"][0]["image"].startswith("http://localhost/")
    assert second["banners"][0]["image"].startswith("http://testserver/")


# --- scheduled work ---------------------------------------------------------


def test_expired_packs_are_switched_off(client, subscriber):
    from datetime import timedelta

    from django.utils import timezone

    from api.packs.models import PackActivation

    client.pay("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"})
    client.pay("/api/packs/internet/purchase/", {"pack_id": "daily-1gb"})
    PackActivation.objects.filter(pack_id="unlimited-1h").update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    assert expire_activations() == 1
    states = dict(PackActivation.objects.values_list("pack_id", "status"))
    assert states == {"unlimited-1h": "expired", "daily-1gb": "active"}
    assert expire_activations() == 0


def test_an_expired_auto_renewing_pack_can_be_activated_again(client):
    from datetime import timedelta

    from django.utils import timezone

    from api.packs.models import PackActivation

    activate = ("/api/packs/social/tehsil/activate/", {"plan_id": "10gb"})
    assert client.pay(*activate).status_code == 201
    assert client.pay(*activate).status_code == 409
    PackActivation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert client.pay(*activate).status_code == 201


def test_old_idempotency_keys_are_purged(client, settings):
    from datetime import timedelta

    from django.utils import timezone

    from api.billing.models import IdempotencyKey
    from api.billing.tasks import purge_idempotency_keys

    old = "5f0c2b9e-7a54-4c2b-9d0e-1f3a5b7c9d11"
    client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "1.00"}, key=old)
    client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "1.00"})
    IdempotencyKey.objects.filter(key=old).update(created_at=timezone.now() - timedelta(days=8))

    assert purge_idempotency_keys() == 1
    assert not IdempotencyKey.objects.filter(key=old).exists()
    assert IdempotencyKey.objects.count() == 1
