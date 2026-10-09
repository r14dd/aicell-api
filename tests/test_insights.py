"""Insights: the figures, each detector against data small enough to check by hand,
the delivery policy and the endpoints."""

from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from api.billing.models import SavedCard, Transaction, Wallet
from api.insights import advisor, services
from api.insights.catalogue import Catalogue
from api.insights.metrics import metrics
from api.insights.models import Insight
from api.packs.models import InternetPack, PackActivation
from api.seeding import DEMO_INSIGHT_ID, seed_test_numbers
from api.tariffs.models import SubscriberTariff
from api.usage import services as usage
from api.users.models import Subscriber

from .conftest import OTHER_INSIGHT_ID, client_for

GB = 1024
ZONE = timezone.get_default_timezone()
NOW = datetime(2026, 6, 15, 12, 0, tzinfo=ZONE)  # a Monday noon in Baku
TODAY = NOW.date()


def at(days_ago: int, hour: int = 12) -> datetime:
    return datetime.combine(TODAY - timedelta(days=days_ago), time(hour), tzinfo=ZONE)


def person(
    msisdn="994550009001",
    *,
    remaining="16.00",
    total=16,
    days_left: float = 10,
    balance="50.00",
    card=True,
    **tariff,
):
    """A subscriber on IsteSen (19.10, 30 days) whose period ends in `days_left` days."""
    subscriber = Subscriber.objects.create_user(msisdn)
    Wallet.objects.create(subscriber=subscriber, balance=Decimal(balance))
    if card:
        SavedCard.objects.create(
            subscriber=subscriber, brand="visa", last4="4471", expiry="12/28", is_default=True
        )
    renews = NOW + timedelta(days=days_left)
    SubscriberTariff.objects.create(
        subscriber=subscriber,
        activated_at=renews - timedelta(days=30),
        last_payment_at=renews - timedelta(days=30),
        next_payment_at=renews,
        data_remaining_gb=Decimal(remaining),
        data_total_gb=total,
        **tariff,
    )
    return subscriber


def use(subscriber, days: dict[int, dict], **every_day):
    """Record usage: `{days_ago: {app: MB}}`, with the same minutes etc. on each day."""
    usage.record_days(
        subscriber,
        [usage.Day(TODAY - timedelta(days=ago), apps, **every_day) for ago, apps in days.items()],
    )


def bought(subscriber, slug, days_ago, kind="internet"):
    pack = InternetPack.objects.get(slug=slug)
    tx = Transaction.objects.create(
        subscriber=subscriber,
        kind="purchase",
        title=pack.label,
        amount=-pack.price,
        created_at=at(days_ago),
    )
    return PackActivation.objects.create(
        subscriber=subscriber,
        transaction=tx,
        kind=kind,
        pack_id=slug,
        label=pack.label,
        activated_at=at(days_ago),
        expires_at=at(days_ago) + timedelta(hours=pack.hours),
    )


def found(subscriber, kind=None):
    results = services.findings(subscriber, NOW)
    if kind is None:
        return results
    return next((finding for finding in results if finding.kind == kind), None)


def refs(finding):
    return [offer["ref"] for offer in finding.offers]


@pytest.fixture
def world(catalogue):
    """The seeded catalogue: internet packs from 0.50 to 35.00, social plans, DigiMax and Premium+."""


# --- metrics ------------------------------------------------------------------


def test_metrics_add_up(world):
    subscriber = person(remaining="4.00", days_left=10, balance="7.00")
    # 7 GB in the last 7 days, half of it YouTube; 3 GB of Instagram 20 days ago.
    use(subscriber, {ago: {"youtube": 512, "other": 512} for ago in range(7)}, call_minutes=3)
    use(subscriber, {20: {"instagram_facebook": 3 * GB}})
    m = metrics(subscriber, NOW)

    assert m.burn_mb_day == GB
    assert m.days_left == 10
    assert m.days_to_empty == 4  # 4 GB left at 1 GB a day
    assert m.gap_mb == 6 * GB  # ten days need 10 GB, 4 are left
    assert m.used_share == 0.75
    assert m.data_mb == 10 * GB
    assert m.video_share == pytest.approx(0.35)
    assert m.social_share == pytest.approx(0.30)
    assert m.renewal_shortfall == Decimal("12.10")  # 19.10 against 7.00
    # 21 days of history stand for a month: 10 GB x 30 / 21
    assert m.span_days == 21
    assert m.data_mb_month == pytest.approx(10 * GB * 30 / 21)
    assert m.minutes_month == pytest.approx(21 * 30 / 21)


def test_no_tariff_no_metrics(world):
    subscriber = Subscriber.objects.create_user("994550009002")
    assert metrics(subscriber, NOW) is None
    assert services.findings(subscriber, NOW) == []
    assert services.refresh(subscriber, NOW) == []


def test_catalogue_is_ranked_from_the_tables(world):
    catalogue = Catalogue.load()
    weekly = catalogue.pack("weekly-5gb")
    assert (weekly.price, weekly.data_mb, weekly.per_gb) == (
        Decimal("5.00"),
        5 * GB,
        Decimal("1.00"),
    )
    assert catalogue.pack("unlimited-1h").per_gb is None
    assert catalogue.overage_per_mb == Decimal("0.05")
    assert [option.target_id for option in catalogue.sized_internet()][:2] == [
        "daily-500mb",
        "daily-1gb",
    ]
    # a pack switched off in the admin is not offered, but its history still resolves
    InternetPack.objects.filter(slug="weekly-5gb").update(is_active=False)
    catalogue = Catalogue.load()
    assert "weekly-5gb" not in [option.target_id for option in catalogue.sized_internet()]
    assert catalogue.pack("weekly-5gb") is not None


# --- detectors ----------------------------------------------------------------


def test_renewal_shortfall(world):
    subscriber = person(days_left=1.5, balance="16.21")
    finding = found(subscriber, "renewal_shortfall")
    assert finding.severity == "urgent"
    assert finding.evidence == {
        "balance": "16.21",
        "price": "19.10",
        "shortfall": "2.89",
        "renews_at": "2026-06-17T00:00:00+04:00",
        "has_card": True,
    }
    assert finding.offers == [
        {
            "ref": "top_up",
            "kind": "top_up",
            "target_id": "",
            "price": "3.00",  # the shortfall rounded up to a whole manat
            "task": {"name": "topUp", "params": {"amount": "3.00"}},
        }
    ]


def test_renewal_shortfall_offers_credit_without_a_card(world):
    finding = found(person(days_left=1, balance="0.00", card=False), "renewal_shortfall")
    assert refs(finding) == ["top_up", "kredit:simkredit"]
    assert finding.offers[0]["price"] == "20.00"


@pytest.mark.parametrize("days_left,balance", [(2.5, "0.00"), (1, "19.10"), (1, "50.00")])
def test_no_shortfall_when_there_is_time_or_money(world, days_left, balance):
    assert found(person(days_left=days_left, balance=balance), "renewal_shortfall") is None


def test_forecast_gap(world):
    subscriber = person(remaining="2.00", days_left=10)
    use(subscriber, {ago: {"other": GB} for ago in range(7)})
    finding = found(subscriber, "forecast_gap")
    assert finding.severity == "info"
    assert finding.evidence == {
        "remaining_gb": 2.0,
        "days_left": 10,
        "burn_gb_day": 1.0,
        "empty_on": "2026-06-17",  # two days from now
        "gap_gb": 8.0,
        "need_gb": 8.8,  # the gap with 10% headroom
    }
    # 8.8 GB: the 20 GB pack is the cheapest that holds it; 5 GB for 5.00 is the budget option
    assert refs(finding) == ["internet:hv-20gb", "internet:weekly-5gb"]
    assert finding.offers[0]["price"] == "15.00"
    assert finding.offers[0]["per_gb"] == "0.75"
    assert finding.offers[0]["task"] == {
        "name": "buyPack",
        "params": {"kind": "internet", "pack_id": "hv-20gb"},
    }


def test_forecast_gap_prefers_a_pack_that_lasts(world):
    # 1.3 GB short over four days: daily-1gb is too small, weekly-2gb holds it and lasts.
    subscriber = person(remaining="4.00", days_left=8)
    use(subscriber, {ago: {"other": 650} for ago in range(7)})
    finding = found(subscriber, "forecast_gap")
    assert finding.evidence["gap_gb"] == 1.1
    assert refs(finding)[0] == "internet:weekly-2gb"


@pytest.mark.parametrize(
    "remaining,days_left,daily",
    [
        ("8.00", 10, GB),  # will not last, but half the tariff is still there
        ("4.00", 3, GB),  # lasts until the renewal
        ("0.00", 10, GB),  # already empty: that is `overage`
    ],
)
def test_no_forecast_gap(world, remaining, days_left, daily):
    subscriber = person(remaining=remaining, days_left=days_left)
    use(subscriber, {ago: {"other": daily} for ago in range(7)})
    assert found(subscriber, "forecast_gap") is None


def test_overage(world):
    subscriber = person(remaining="0.00", days_left=5)
    use(subscriber, {ago: {"other": GB} for ago in range(1, 7)})
    use(subscriber, {0: {"other": GB}}, overage_mb=50, overage_amount=Decimal("2.50"))
    finding = found(subscriber, "overage")
    assert finding.severity == "urgent"
    assert finding.evidence == {
        "overage_mb": 50,
        "overage_amount": "2.50",
        "rate_per_mb": "0.05",
        "burn_gb_day": 1.0,
        "days_left": 5,
    }
    # now: the cheapest day pack; for the five days left: 5 GB that lasts a week
    assert refs(finding) == ["internet:daily-500mb", "internet:weekly-5gb"]
    # a day's 1 GB costs 51.20 per megabyte; the packs cost 0.50 and 5.00
    assert finding.offers[0]["saving"] == "50.70"
    assert finding.offers[1]["saving"] == "251.00"
    assert found(subscriber)[0].kind == "overage"  # urgent findings come first


@pytest.mark.parametrize(
    "remaining,days_left,overage_mb", [("0.50", 5, 50), ("0.00", 0.5, 50), ("0.00", 5, 20)]
)
def test_no_overage(world, remaining, days_left, overage_mb):
    subscriber = person(remaining=remaining, days_left=days_left)
    use(subscriber, {0: {"other": GB}}, overage_mb=overage_mb)
    assert found(subscriber, "overage") is None


def test_video_heavy(world):
    subscriber = person()
    bought(subscriber, "hv-20gb", days_ago=6)
    # the 20 GB are gone on the third day: 3 x 7 GB, five of every seven on YouTube
    use(subscriber, {ago: {"youtube": 5 * GB, "tiktok": GB, "other": GB} for ago in (6, 5, 4)})
    finding = found(subscriber, "video_heavy")
    assert finding.evidence == {
        "pack": {
            "id": "hv-20gb",
            "data_gb": 20.0,
            "price": "15.00",
            "per_gb": "0.75",
            "activated_at": "2026-06-09",
            "emptied_at": "2026-06-11",
            "days": 3,
        },
        "by_app_gb": {"other": 3.0, "tiktok": 3.0, "youtube": 15.0},
        "video_share": 0.86,
    }
    youtube, tiktok = finding.offers
    assert youtube["ref"] == "social:youtube:10gb"  # no plan holds 15 GB: the biggest one
    assert tiktok["ref"] == "social:tiktok:10gb"  # the 2 GB plan lasts one day
    assert tiktok["task"] == {"name": "activatePack", "params": {"slug": "tiktok", "plan": "10gb"}}
    # 10 GB inside the 20 GB pack cost 10 x 0.75; the plan itself costs 4.00
    assert (tiktok["price"], tiktok["same_gb_in_pack"], tiktok["saving"]) == (
        "4.00",
        "7.50",
        "3.50",
    )


def test_no_video_heavy_without_video_or_a_fast_pack(world):
    slow = person("994550009003")
    bought(slow, "hv-20gb", days_ago=6)
    use(slow, {ago: {"youtube": 2 * GB} for ago in (6, 5, 4)})  # 6 GB in three days
    assert found(slow, "video_heavy") is None

    other_apps = person("994550009004")
    bought(other_apps, "hv-20gb", days_ago=6)
    use(other_apps, {ago: {"youtube": 3 * GB, "other": 4 * GB} for ago in (6, 5, 4)})
    assert found(other_apps, "video_heavy") is None  # 43% video

    small = person("994550009005")
    bought(small, "weekly-2gb", days_ago=6)
    use(small, {ago: {"youtube": 5 * GB} for ago in (6, 5, 4)})
    assert found(small, "video_heavy") is None  # a 2 GB pack is not a high-volume one


def test_repeat_packs(world):
    subscriber = person(days_left=10)  # the period began 20 days ago
    for ago in (15, 8, 2):
        bought(subscriber, "weekly-5gb", days_ago=ago)
    bought(subscriber, "weekly-5gb", days_ago=25)  # the period before
    use(subscriber, {ago: {"other": 800} for ago in range(30)})
    finding = found(subscriber, "repeat_packs")
    assert [pack["date"] for pack in finding.evidence["packs"]] == [
        "2026-06-13",
        "2026-06-07",
        "2026-05-31",
    ]
    assert finding.evidence["packs_total"] == "15.00"
    assert finding.evidence["tariff_price"] == "19.10"
    # four packs in the 30 days of history: 19.10 + 20.00
    assert finding.evidence["monthly_spend"] == "39.10"
    assert finding.evidence["data_gb_month"] == 23.4
    # 23.4 GB a month: DigiMax 25GB is the cheapest plan that holds it
    assert refs(finding) == ["tariff:digimax-25", "tariff:premium-60"]
    assert finding.offers[0]["saving"] == "9.10"
    assert finding.offers[1]["saving"] is None  # dearer than what is paid now
    assert finding.offers[0]["task"] == {"name": "changeTariff", "params": {"plan": "digimax-25"}}


def test_one_pack_is_not_a_habit(world):
    subscriber = person(days_left=10)
    bought(subscriber, "weekly-5gb", days_ago=3)
    bought(subscriber, "weekly-5gb", days_ago=25)
    assert found(subscriber, "repeat_packs") is None


def test_social_heavy_redesigns_istesen(world):
    subscriber = person()
    use(
        subscriber,
        {ago: {"instagram_facebook": 100, "tiktok": 150, "other": 50} for ago in range(30)},
        call_minutes=1,
    )
    finding = found(subscriber, "social_heavy")
    assert finding.evidence == {
        "by_app_gb": {"instagram_facebook": 2.9, "other": 1.5, "tiktok": 4.4},
        "social_share": 0.33,  # below 40%, but TikTok alone is over 4 GB a month
        "tiktok_gb_month": 4.4,
    }
    redesign, tiktok, instagram = finding.offers
    # Instagram 2.9 -> 3, TikTok 4.4 -> 5, the other 1.5 GB x 1.3 -> 2, 30 minutes -> 30
    values = {"instagramFb": 3, "youtube": 0, "tiktok": 5, "internet": 2, "calls": 30}
    assert redesign["values"] == values
    assert redesign["task"] == {"name": "applyRedesign", "params": values}
    # 19.10 + 0.50 x (2 - 16 + 3 + 0 + 5)
    assert (redesign["price"], redesign["saving"], redesign["saving_year"]) == (
        "16.10",
        "3.00",
        "36.00",
    )
    assert (tiktok["ref"], instagram["ref"]) == (
        "social:tiktok:10gb",
        "social:instagram-facebook:5gb",
    )


def test_no_social_heavy_for_general_browsing(world):
    subscriber = person()
    use(subscriber, {ago: {"other": 300, "instagram_facebook": 50} for ago in range(30)})
    assert found(subscriber, "social_heavy") is None


def test_underused(world):
    subscriber = person(days_left=10)  # periods of 30 days; this one began 20 days ago
    use(subscriber, {ago: {"other": 100} for ago in range(20, 115)})  # 3 GB of 16 each period
    finding = found(subscriber, "underused")
    assert finding.evidence["included_gb"] == 16.0
    assert finding.evidence["periods"] == [
        {"start": "2026-04-26", "end": "2026-05-25", "used_gb": 2.9, "unused_gb": 13.1},
        {"start": "2026-03-27", "end": "2026-04-25", "used_gb": 2.9, "unused_gb": 13.1},
        {"start": "2026-02-25", "end": "2026-03-26", "used_gb": 2.9, "unused_gb": 13.1},
    ]
    redesign, plan = finding.offers
    # 2.9 GB with 10% headroom -> 4 GB of internet: 19.10 - 12 x 0.50
    assert redesign["values"]["internet"] == 4
    assert (redesign["price"], redesign["saving"], redesign["saving_year"]) == (
        "13.10",
        "6.00",
        "72.00",
    )
    assert (plan["ref"], plan["saving"]) == ("tariff:digimax-5", "7.10")


def test_underused_needs_three_full_periods(world):
    two = person("994550009006", days_left=10)
    use(two, {ago: {"other": 100} for ago in range(20, 85)})
    assert found(two, "underused") is None

    busy = person("994550009007", days_left=10)
    use(busy, {ago: {"other": 100} for ago in range(20, 115)})
    use(busy, {ago: {"other": 400} for ago in range(50, 80)})  # 11.7 GB in the middle period
    assert found(busy, "underused") is None


def test_roaming(world):
    subscriber = person()
    use(subscriber, {1: {}}, roaming_data_mb=300)
    finding = found(subscriber, "roaming")
    assert finding.evidence == {"roaming_mb": 300, "days": 3}
    assert refs(finding) == ["roaming:r-5gb", "roaming:r-2gb"]  # cheapest gigabyte first
    assert finding.offers[0]["task"] == {
        "name": "buyPack",
        "params": {"kind": "roaming", "pack_id": "r-5gb"},
    }

    PackActivation.objects.create(
        subscriber=subscriber,
        kind="roaming",
        pack_id="r-2gb",
        label="Roaming 2 GB",
        activated_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=9),
    )
    assert found(subscriber, "roaming") is None


def test_nothing_is_found_for_a_quiet_subscriber(world):
    subscriber = person()
    use(subscriber, {ago: {"other": 300} for ago in range(30)})
    assert found(subscriber) == []


# --- storing ------------------------------------------------------------------


@pytest.fixture
def short(world):
    """A subscriber whose renewal is tomorrow and not covered: one urgent insight."""
    return person(days_left=1, balance="16.21")


def test_refresh_keeps_one_open_insight_per_kind(short):
    (first,) = services.refresh(short, NOW)
    assert (first.kind, first.status, first.severity) == ("renewal_shortfall", "new", "urgent")
    assert first.expires_at == NOW + timedelta(days=7)

    Wallet.objects.filter(subscriber=short).update(balance=Decimal("18.00"))
    (again,) = services.refresh(short, NOW + timedelta(hours=1))
    assert again.id == first.id  # the same insight, with the new figures
    assert again.evidence["shortfall"] == "1.10"
    assert again.offers[0]["price"] == "2.00"
    assert Insight.objects.filter(subscriber=short).count() == 1


def test_an_insight_is_closed_when_it_stops_being_true(short):
    (insight,) = services.refresh(short, NOW)
    Wallet.objects.filter(subscriber=short).update(balance=Decimal("25.00"))  # topped up
    assert services.refresh(short, NOW + timedelta(hours=1)) == []
    insight.refresh_from_db()
    assert insight.status == "resolved"
    assert services.deliverable(short, NOW + timedelta(hours=1)) == []


def test_a_dismissed_kind_is_silent_for_14_days(short):
    (insight,) = services.refresh(short, NOW)
    dismissed = services.dismiss(short, insight.id, NOW)
    assert dismissed.status == "dismissed"
    assert dismissed.snoozed_until == NOW + timedelta(days=14)
    # the renewal date is moved along so the condition still holds two weeks later
    SubscriberTariff.objects.filter(subscriber=short).update(
        next_payment_at=NOW + timedelta(days=15)
    )
    assert services.refresh(short, NOW + timedelta(days=13, hours=23)) == []
    (new,) = services.refresh(short, NOW + timedelta(days=14, hours=1))
    assert new.id != insight.id and new.status == "new"


def test_an_accepted_kind_is_silent_for_two_days(short):
    (insight,) = services.refresh(short, NOW)
    accepted = services.accept(short, insight.id, now=NOW)
    assert (accepted.status, accepted.accepted_offer) == ("accepted", 0)
    assert services.refresh(short, NOW + timedelta(hours=1)) == []
    assert services.accept(short, insight.id, now=NOW + timedelta(hours=2)).decided_at == NOW


def test_an_insight_lapses_after_seven_days(short):
    (insight,) = services.refresh(short, NOW)
    SubscriberTariff.objects.filter(subscriber=short).update(
        next_payment_at=NOW + timedelta(days=8)
    )
    later = NOW + timedelta(days=7, minutes=1)
    (new,) = services.refresh(short, later)
    insight.refresh_from_db()
    assert insight.status == "expired"
    assert new.id != insight.id


def test_the_nightly_run_covers_everyone(world):
    person("994550009008", days_left=1, balance="0.00")
    person("994550009009", days_left=1, balance="0.00")
    person("994550009010")
    assert services.refresh_all(NOW) == 2
    assert services.refresh_all(NOW) == 2  # a second run adds nothing
    assert Insight.objects.count() == 2


# --- delivery -----------------------------------------------------------------


@pytest.fixture
def busy(world):
    """A subscriber with one urgent and two info insights waiting."""
    subscriber = person(days_left=1, balance="0.00")
    use(subscriber, {0: {}}, roaming_data_mb=300)
    use(subscriber, {ago: {"instagram_facebook": 200, "other": 100} for ago in range(1, 30)})
    kinds = [insight.kind for insight in services.refresh(subscriber, NOW)]
    assert kinds == ["renewal_shortfall", "social_heavy", "roaming"]
    return subscriber


def kinds(subscriber, now):
    return [insight.kind for insight in services.deliverable(subscriber, now)]


def test_one_info_insight_per_48_hours(busy):
    assert kinds(busy, NOW) == ["renewal_shortfall", "social_heavy"]
    assert kinds(busy, NOW + timedelta(hours=47)) == ["renewal_shortfall", "social_heavy"]
    # two days on, the first is still open, so it stays the one being shown
    assert kinds(busy, NOW + timedelta(hours=49)) == ["renewal_shortfall", "social_heavy"]


def test_the_next_info_insight_waits_its_turn(busy):
    assert kinds(busy, NOW) == ["renewal_shortfall", "social_heavy"]
    social = Insight.objects.get(subscriber=busy, kind="social_heavy")
    services.dismiss(busy, social.id, NOW + timedelta(hours=1))
    assert kinds(busy, NOW + timedelta(hours=2)) == ["renewal_shortfall"]  # urgent is not limited
    assert kinds(busy, NOW + timedelta(hours=49)) == ["renewal_shortfall", "roaming"]


def test_nothing_is_delivered_at_night(busy, settings):
    settings.INSIGHTS_QUIET_HOURS = (23, 8)
    night = datetime(2026, 6, 15, 23, 30, tzinfo=ZONE)
    early = datetime(2026, 6, 16, 7, 59, tzinfo=ZONE)
    morning = datetime(2026, 6, 16, 8, 0, tzinfo=ZONE)
    assert kinds(busy, night) == [] and kinds(busy, early) == []
    assert kinds(busy, morning) == ["renewal_shortfall", "social_heavy"]
    assert Insight.objects.get(subscriber=busy, kind="social_heavy").delivered_at == morning


def test_lapsed_and_answered_insights_are_not_delivered(busy):
    urgent = Insight.objects.get(subscriber=busy, kind="renewal_shortfall")
    services.accept(busy, urgent.id, now=NOW)
    assert kinds(busy, NOW) == ["social_heavy"]
    assert kinds(busy, NOW + timedelta(days=8)) == []


# --- advisor ------------------------------------------------------------------


def test_advisor_compares_the_month_with_its_alternatives(world):
    subscriber = person(days_left=10)
    for ago in (40, 12):
        bought(subscriber, "hv-20gb", days_ago=ago)  # one 15.00 pack a month
    use(
        subscriber,
        {
            ago: {
                "youtube": 256,
                "tiktok": 150,
                "instagram_facebook": 60,
                "whatsapp": 30,
                "other": 256,
            }
            for ago in range(60)
        },
        call_minutes=1,
    )
    advice = advisor.advise(metrics(subscriber, NOW), Catalogue.load())

    assert advice["period_days"] == 60
    assert advice["profile"] == {
        "data_gb_month": 22.0,
        "by_app_gb": {
            "instagram_facebook": 1.8,
            "other": 7.5,
            "tiktok": 4.4,
            "whatsapp": 0.9,
            "youtube": 7.5,
        },
        "minutes_month": 30,
    }
    assert advice["current"] == {
        "tariff": "IsteSen",
        "price": "19.10",
        "packs_month": "15.00",
        "total_month": "34.10",
    }
    plus, plan, bigger = advice["candidates"]
    # YouTube 7.5 -> 8, TikTok 4.4 -> 5, Instagram 1.8 -> 2, the other 7.5 GB x 1.3 -> 10;
    # WhatsApp fits in the 1 GB of messaging every tariff includes.
    values = {"instagramFb": 2, "youtube": 8, "tiktok": 5, "internet": 10, "calls": 30}
    assert plus["id"] == "istesen-plus" and plus["redesign"] == values
    # 19.10 + 0.50 x (10 - 16 + 2 + 8 + 5)
    assert (plus["price"], plus["total_month"]) == ("23.60", "23.60")
    assert (plus["saving_month"], plus["saving_year"]) == ("10.50", "126.00")
    assert (plus["data_gb"], plus["minutes"]) == (25, 30)
    assert plus["task"] == {"name": "applyRedesign", "params": values}
    assert (plan["id"], plan["price"], plan["saving_month"]) == ("digimax-25", "30.00", "4.10")
    assert plan["task"] == {"name": "changeTariff", "params": {"plan": "digimax-25"}}
    assert (bigger["id"], bigger["rejected"]) == ("premium-60", "usage_x2.7")
    assert advice["recommended"] == "istesen-plus"
    assert advice["effective_from"] == "2026-06-25"


def test_advisor_leaves_a_fitting_tariff_alone(world):
    subscriber = person()
    use(subscriber, {ago: {"other": 400} for ago in range(30)}, call_minutes=1)
    advice = advisor.advise(metrics(subscriber, NOW), Catalogue.load())
    plus = advice["candidates"][0]
    # 11.7 GB x 1.3 -> 16 GB: the same tariff as now, nothing to gain
    assert plus["redesign"]["internet"] == 16 and plus["saving_month"] == "0.00"
    assert advice["recommended"] == "current"


def test_advisor_passes_to_a_plan_when_the_constructor_is_too_small(world):
    subscriber = person()
    use(subscriber, {ago: {"other": 700} for ago in range(30)})  # 20.5 GB of general internet
    advice = advisor.advise(metrics(subscriber, NOW), Catalogue.load())
    plus, plan = advice["candidates"][:2]
    assert plus["rejected"] == "does_not_cover"  # general internet stops at 16 GB
    assert plan["id"] == "digimax-25"
    # 30.00 against 19.10 is no saving, so the answer is to stay
    assert advice["recommended"] == "current"


# --- endpoints ----------------------------------------------------------------


def test_the_demo_subscriber_has_an_insight(client):
    body = client.get("/api/insights/").json()
    (insight,) = body["results"]
    assert insight["id"] == DEMO_INSIGHT_ID
    assert (insight["kind"], insight["severity"], insight["status"]) == (
        "social_heavy",
        "info",
        "new",
    )
    assert insight["evidence"]["social_share"] == 0.55
    assert set(insight) == {
        "id", "kind", "severity", "status", "created_at", "expires_at", "evidence", "offers",
        "recommended",
    }  # fmt: skip
    redesign, instagram = insight["offers"]
    assert redesign["ref"] == "redesign" and redesign["label"] == "IsteSen+"
    assert redesign["price"] == "18.10" and redesign["saving"] == "1.00"
    assert redesign["validity"] is None
    assert instagram == {
        "ref": "social:instagram-facebook:5gb",
        "label": "Instagram & Facebook 5 GB",
        "price": "3.00",
        "validity": "30 d.",
        "data_gb": 5.0,
        "per_gb": "0.60",
        "saving": None,
        "task": {"name": "activatePack", "params": {"slug": "instagram-facebook", "plan": "5gb"}},
    }
    assert insight["recommended"] == 0
    assert "+04:00" in insight["created_at"]


def test_offer_labels_follow_the_language(client):
    def labels(language):
        results = client.get("/api/insights/", HTTP_ACCEPT_LANGUAGE=language).json()["results"]
        return [(offer["label"], offer["validity"]) for offer in results[0]["offers"]]

    assert labels("az")[1] == ("Instagram & Facebook 5 GB", "30 gün")


def test_an_offer_that_left_the_catalogue_is_not_shown(client, subscriber):
    Insight.objects.filter(id=DEMO_INSIGHT_ID).update(
        offers=[
            {"ref": "internet:gone", "kind": "internet_pack", "target_id": "gone", "price": "1.00",
             "hours": 24, "task": {"name": "buyPack", "params": {}}},
        ],
        delivered_at=timezone.now(),
    )  # fmt: skip
    # the stored offer cannot be had; the detector then rewrites the insight with live ones
    refreshed = client.get("/api/insights/").json()["results"]
    assert [offer["ref"] for offer in refreshed[0]["offers"]][0] == "redesign"


def test_seen_accept_and_the_task_that_follows(client):
    client.get("/api/insights/")
    seen = client.post_json(f"/api/insights/{DEMO_INSIGHT_ID}/seen/")
    assert (seen.status_code, seen.json()["status"]) == (200, "seen")

    accepted = client.post_json(f"/api/insights/{DEMO_INSIGHT_ID}/accept/")
    assert accepted.status_code == 200, accepted.content
    body = accepted.json()
    assert body["status"] == "accepted"
    assert body["task"]["name"] == "applyRedesign"
    assert client.get("/api/billing/balance/").json()["balance"] == "16.21"  # nothing was charged

    # the task is carried out by the endpoint that owns it
    saved = client.post_json("/api/tariffs/my/redesign/", {"values": body["task"]["params"]})
    assert saved.status_code == 200 and saved.json()["estimate"] == "18.10"
    # answered, so it is no longer handed out, and its kind stays quiet
    assert client.get("/api/insights/").json() == {"results": []}
    assert (
        client.post_json(f"/api/insights/{DEMO_INSIGHT_ID}/dismiss/").json()["status"] == "accepted"
    )


def test_accept_takes_the_offer_asked_for(client):
    body = client.post_json(f"/api/insights/{DEMO_INSIGHT_ID}/accept/", {"offer": 1}).json()
    assert body["task"] == {
        "name": "activatePack",
        "params": {"slug": "instagram-facebook", "plan": "5gb"},
    }
    for bad in (2, -1, "x"):
        response = client.post_json(f"/api/insights/{DEMO_INSIGHT_ID}/accept/", {"offer": bad})
        assert response.status_code == 400
        assert response.json()["code"] == "validation_error"


def test_dismiss(client):
    response = client.post_json(f"/api/insights/{DEMO_INSIGHT_ID}/dismiss/")
    assert (response.status_code, response.json()["status"]) == (200, "dismissed")
    assert client.get("/api/insights/").json() == {"results": []}
    assert Insight.objects.filter(kind="social_heavy").count() == 1  # not written again


def test_insights_belong_to_their_subscriber(client, other, other_client):
    assert [i["id"] for i in other_client.get("/api/insights/").json()["results"]] == [
        OTHER_INSIGHT_ID
    ]
    for action in ("seen", "accept", "dismiss"):
        assert (
            other_client.post_json(f"/api/insights/{DEMO_INSIGHT_ID}/{action}/").status_code == 404
        )
    assert Insight.objects.get(id=DEMO_INSIGHT_ID).status == "new"
    assert client.post_json("/api/insights/999999/seen/").status_code == 404


def test_endpoints_need_credentials(anon, subscriber):
    assert anon.get("/api/insights/").status_code == 401
    assert anon.get("/api/insights/advisor/").status_code == 401
    assert anon.post(f"/api/insights/{DEMO_INSIGHT_ID}/accept/").status_code == 401


def test_a_purchase_is_seen_by_the_next_call(client, subscriber):
    """No scheduler is needed for an event: the detectors run when the app asks."""
    Insight.objects.filter(subscriber=subscriber).delete()
    for _ in range(2):
        assert (
            client.pay("/api/packs/internet/purchase/", {"pack_id": "daily-1gb"}).status_code == 201
        )
    SubscriberTariff.objects.filter(subscriber=subscriber).update(
        last_payment_at=timezone.now() - timedelta(days=1)
    )
    kinds_now = set(Insight.objects.filter(subscriber=subscriber).values_list("kind", flat=True))
    assert "repeat_packs" not in kinds_now
    client.get("/api/insights/")
    assert Insight.objects.filter(subscriber=subscriber, kind="repeat_packs").exists()


def test_advisor_endpoint(client, subscriber):
    body = client.get("/api/insights/advisor/").json()
    assert set(body) == {
        "period_days", "profile", "current", "candidates", "recommended", "effective_from",
    }  # fmt: skip
    assert body["current"] == {
        "tariff": "IsteSen",
        "price": "19.10",
        "packs_month": "0.00",
        "total_month": "19.10",
    }
    assert body["candidates"][0]["price"] == "18.10"
    assert body["recommended"] == "istesen-plus"
    assert body["effective_from"] == "2026-10-25"

    SubscriberTariff.objects.filter(subscriber=subscriber).delete()
    assert client.get("/api/insights/advisor/").status_code == 404
    assert client.get("/api/insights/").json() == {"results": []}


def test_the_seeded_personas_get_what_their_stories_say(catalogue):
    heavy, voice, roamer, balanced = seed_test_numbers()
    assert [f.kind for f in services.findings(heavy)] == ["repeat_packs"]
    assert services.findings(voice) == []
    assert services.findings(balanced) == []
    top = services.findings(heavy)[0].offers[0]
    assert (top["ref"], top["price"]) == ("tariff:digimax-25", "30.00")
    assert client_for(roamer).get("/api/insights/").status_code == 200
