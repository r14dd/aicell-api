"""A database seeded before the usage work keeps working after it is migrated."""

import pytest
from django.core.management import call_command

from api.packs.models import InternetPack, RoamingPack, SocialPlan
from api.seeding import TEST_NUMBERS
from api.tariffs.models import PriceGroup, TariffPlan
from api.usage import recommendations
from api.users.models import Subscriber


@pytest.fixture
def old_catalogue(catalogue):
    """The catalogue as it was before plans and packs had numbers."""
    TariffPlan.objects.update(data_mb=None, minutes=None, sms=None, roaming_mb=0)
    InternetPack.objects.update(data_mb=None)
    SocialPlan.objects.update(data_mb=0)
    RoamingPack.objects.update(data_mb=0)
    for group in PriceGroup.objects.all():
        for field in ("rows", "rows_en", "rows_az", "rows_ru"):
            setattr(
                group,
                field,
                [{"label": r["label"], "price": r["price"]} for r in getattr(group, field)],
            )
        group.save()


def run_backfill():
    from importlib import import_module

    from django.apps import apps

    for app in ("tariffs", "packs"):
        import_module(f"api.{app}.migrations.0002_included_amounts").fill_amounts(apps, None)


def test_the_migration_fills_what_the_old_rows_lack(old_catalogue):
    assert recommendations.rates()["data_mb"] == 0  # nothing to price with yet
    run_backfill()
    from django.core.cache import cache

    cache.clear()
    plan = TariffPlan.objects.get(slug="digimax-25")
    assert (plan.data_mb, plan.minutes, plan.sms) == (25600, 500, 200)
    assert TariffPlan.objects.get(slug="premium-100").minutes is None  # unlimited stays empty
    assert InternetPack.objects.get(slug="hv-20gb").data_mb == 20480
    assert InternetPack.objects.get(slug="unlimited-1h").data_mb is None
    assert SocialPlan.objects.get(pack__slug="youtube", slug="10gb").data_mb == 10240
    assert RoamingPack.objects.get(slug="r-2gb").data_mb == 2048
    assert recommendations.rates()["data_mb"] > 0
    group = PriceGroup.objects.order_by("order").first()
    assert [row["key"] for row in group.rows_az] == ["data_mb", "minute", "sms", "intl_sms"]


def test_the_seed_then_runs_on_the_old_database(old_catalogue):
    """What a container start does: migrate, then a plain `seed`."""
    run_backfill()
    call_command("seed")
    assert Subscriber.objects.filter(msisdn__in=TEST_NUMBERS).count() == 4
    heavy = Subscriber.objects.get(msisdn=TEST_NUMBERS[0])
    assert recommendations.recommend(heavy).recommendations[0].target_id == "hv-20gb"


def test_the_backfill_does_not_rewrite_price_rows_that_have_keys(catalogue):
    before = PriceGroup.objects.order_by("order").first().rows
    run_backfill()
    assert PriceGroup.objects.order_by("order").first().rows == before
