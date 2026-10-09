"""Usage history, the 30-day profile, recommendations and personal offers."""

import json
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from api.assistant import responder
from api.billing.models import Transaction, Wallet
from api.content.models import Notification
from api.packs.models import PackActivation
from api.seeding import DEMO_OFFER_ID, TEST_NUMBERS, seed_test_numbers
from api.tariffs.models import SubscriberTariff
from api.usage import assistant, offers, recommendations, services, taxonomy
from api.usage.models import AppUsage, DailyUsage, OfferRule, PersonalOffer
from api.usage.recommendations import Included, Usage
from api.users.models import Subscriber

from .conftest import OTHER_OFFER_ID, client_for

HEAVY, VOICE, ROAMER, BALANCED = TEST_NUMBERS
DEMO = "994516643342"
ACCEPT = f"/api/usage/offers/{DEMO_OFFER_ID}/accept/"
DECLINE = f"/api/usage/offers/{DEMO_OFFER_ID}/decline/"


@pytest.fixture
def people(subscriber):
    """The five seeded stories, by number."""
    testers = seed_test_numbers()
    return {DEMO: subscriber, **{tester.msisdn: tester for tester in testers}}


def today():
    return timezone.localdate()


def newcomer(plan="digimax-5", msisdn="994550001111") -> Subscriber:
    """A subscriber on a catalogue plan with no usage yet; tests add what they need."""
    from api.tariffs.models import TariffPlan

    person = Subscriber.objects.create_user(msisdn)
    row = TariffPlan.objects.get(slug=plan)
    start = timezone.now() - timedelta(days=10)
    SubscriberTariff.objects.create(
        subscriber=person,
        family="digimax",
        plan_slug=plan,
        title=row.title,
        price=row.price,
        validity_days=28,
        activated_at=start,
        last_payment_at=start,
        next_payment_at=start + timedelta(days=28),
        data_total_gb=row.data_mb // 1024,
        minutes_total=row.minutes,
    )
    Wallet.objects.create(subscriber=person, balance=Decimal("0.00"))
    return person


# --- taxonomy -----------------------------------------------------------------


def test_every_app_belongs_to_exactly_one_category():
    apps = [app for group in taxonomy.CATEGORIES.values() for app in group]
    assert len(apps) == len(set(apps)) == 10
    assert set(taxonomy.CATEGORIES) == {"video", "social", "messaging", "games", "other"}
    assert taxonomy.CATEGORIES["video"] == ("youtube", "kinon")
    assert taxonomy.CATEGORIES["games"] == ("games", "steam")
    assert taxonomy.category_of("telegram") == "messaging"


def test_every_category_and_app_has_a_label_and_a_selling_entry():
    assert set(taxonomy.CATEGORY_LABELS) == set(taxonomy.SELLS) == set(taxonomy.CATEGORIES)
    assert set(taxonomy.APP_LABELS) == set(taxonomy.APPS)
    assert taxonomy.SELLS["games"] == ()  # nothing to sell yet


def test_what_is_sold_for_a_category_exists_in_the_catalogue(subscriber):
    """The mapping must not point at products that are not there."""
    profile = services.profile(subscriber)
    for category, entries in taxonomy.SELLS.items():
        for entry in entries:
            assert recommendations._sold(entry, profile), f"{category}: {entry}"


# --- recording ----------------------------------------------------------------


def test_recording_a_day_twice_changes_nothing(subscriber):
    day = today() - timedelta(days=40)
    for _ in range(2):
        services.record_usage(
            subscriber, day, data_by_app={"youtube": 300, "whatsapp": 50}, call_minutes=7, sms=2
        )
    row = DailyUsage.objects.get(subscriber=subscriber, day=day)
    assert (row.data_mb, row.call_minutes, row.sms) == (350, 7, 2)
    assert AppUsage.objects.filter(subscriber=subscriber, day=day).count() == 2


def test_recording_a_day_again_replaces_it(subscriber):
    day = today() - timedelta(days=40)
    services.record_usage(subscriber, day, data_by_app={"youtube": 300, "whatsapp": 50})
    services.record_usage(subscriber, day, data_by_app={"tiktok": 100}, roaming_data_mb=20)
    row = DailyUsage.objects.get(subscriber=subscriber, day=day)
    assert (row.data_mb, row.roaming_data_mb) == (100, 20)
    apps = dict(
        AppUsage.objects.filter(subscriber=subscriber, day=day).values_list("app", "data_mb")
    )
    assert apps == {"tiktok": 100}


def test_an_unknown_app_is_rejected_and_nothing_is_stored(subscriber):
    day = today() - timedelta(days=40)
    with pytest.raises(taxonomy.UnknownApp):
        services.record_usage(subscriber, day, data_by_app={"youtube": 10, "netflix": 10})
    assert not DailyUsage.objects.filter(subscriber=subscriber, day=day).exists()
    assert not AppUsage.objects.filter(subscriber=subscriber, day=day).exists()


# --- the profile of each persona ----------------------------------------------

PROFILES = {
    HEAVY: {
        "segment": "heavy_data",
        "data_mb": 24000,
        "minutes": 60,
        "sms": 10,
        "roaming_data_mb": 0,
    },
    VOICE: {"segment": "voice_only", "data_mb": 0, "minutes": 92, "sms": 6, "roaming_data_mb": 0},
    ROAMER: {
        "segment": "roamer",
        "data_mb": 6000,
        "minutes": 140,
        "sms": 0,
        "roaming_data_mb": 1800,
    },
    BALANCED: {
        "segment": "balanced",
        "data_mb": 7400,
        "minutes": 150,
        "sms": 40,
        "roaming_data_mb": 0,
    },
    DEMO: {"segment": "balanced", "data_mb": 13000, "minutes": 20, "sms": 6, "roaming_data_mb": 0},
}
#           tariff fee, add-ons (count, amount), roaming (count, amount), other
SPEND = {
    HEAVY: ("12.00", 5, "20.98", 0, "0.00", "0.00"),
    VOICE: ("12.00", 0, "0.00", 0, "0.00", "0.00"),
    ROAMER: ("18.00", 0, "0.00", 4, "40.00", "0.00"),
    BALANCED: ("18.00", 0, "0.00", 0, "0.00", "0.90"),
    DEMO: ("19.10", 0, "0.00", 0, "0.00", "0.00"),
}


@pytest.mark.parametrize("msisdn", list(PROFILES))
def test_profile_totals(people, msisdn):
    profile = services.profile(people[msisdn])
    expected = PROFILES[msisdn]
    assert profile.days == 30 and profile.end == today()
    for name, value in expected.items():
        assert getattr(profile, name) == value, name
    assert sum(data_mb for _, data_mb in profile.by_app) == profile.data_mb


@pytest.mark.parametrize("msisdn", list(SPEND))
def test_profile_spend(people, msisdn):
    spend = services.profile(people[msisdn]).spend
    fee, addon_count, addon_amount, roaming_count, roaming_amount, other = SPEND[msisdn]
    assert spend.tariff_fee == Decimal(fee)
    assert (spend.addon_count, spend.addon_amount) == (addon_count, Decimal(addon_amount))
    assert (spend.roaming_count, spend.roaming_amount) == (roaming_count, Decimal(roaming_amount))
    assert spend.other == Decimal(other)
    assert spend.total == spend.plan_related + spend.other


def test_profile_of_the_heavy_user(people):
    profile = services.profile(people[HEAVY])
    assert profile.by_app[0][0] == "youtube" and profile.share(profile.by_app[0][1]) == 0.62
    assert profile.by_category[0][0] == "video"
    assert (profile.ran_out.day, profile.ran_out.period_days) == (3, 28)
    assert profile.ran_out.date == today() - timedelta(days=18)


def test_profile_of_the_others(people):
    assert services.profile(people[VOICE]).by_app == ()
    assert services.profile(people[VOICE]).ran_out is None
    roamer = services.profile(people[ROAMER])
    assert (roamer.roaming_days, roamer.roaming_minutes) == (9, 45)
    assert services.profile(people[BALANCED]).services == ("missed-call",)
    demo = services.profile(people[DEMO])
    assert demo.by_app[0][0] == "instagram_facebook" and demo.share(demo.by_app[0][1]) == 0.55


def test_a_shorter_window_counts_fewer_days(people):
    week = services.profile(people[BALANCED], days=7)
    month = services.profile(people[BALANCED], days=30)
    assert week.start == today() - timedelta(days=6)
    assert 0 < week.data_mb < month.data_mb
    assert week.minutes == 35  # five a day


@pytest.mark.parametrize(
    "facts,segment",
    [
        (
            {"data_mb": 0, "minutes": 40, "roaming_days": 0, "addon_count": 0, "ran_out": None},
            "voice_only",
        ),
        (
            {"data_mb": 100, "minutes": 30, "roaming_days": 0, "addon_count": 0, "ran_out": None},
            "voice_only",
        ),
        (
            {"data_mb": 101, "minutes": 30, "roaming_days": 0, "addon_count": 0, "ran_out": None},
            "low_usage",
        ),
        (
            {"data_mb": 0, "minutes": 5, "roaming_days": 0, "addon_count": 0, "ran_out": None},
            "low_usage",
        ),
        (
            {"data_mb": 5000, "minutes": 5, "roaming_days": 3, "addon_count": 0, "ran_out": None},
            "roamer",
        ),
        (
            {"data_mb": 5000, "minutes": 5, "roaming_days": 2, "addon_count": 0, "ran_out": None},
            "balanced",
        ),
        (
            {"data_mb": 20480, "minutes": 5, "roaming_days": 0, "addon_count": 0, "ran_out": None},
            "heavy_data",
        ),
        (
            {"data_mb": 5000, "minutes": 5, "roaming_days": 0, "addon_count": 3, "ran_out": None},
            "heavy_data",
        ),
        (
            {"data_mb": 5000, "minutes": 5, "roaming_days": 0, "addon_count": 0, "ran_out": True},
            "heavy_data",
        ),
    ],
)
def test_segment_thresholds(facts, segment):
    assert services.segment_of(**facts) == segment


# --- arithmetic ---------------------------------------------------------------


def test_overage_by_hand(catalogue):
    """880 MB x 0.05 + 50 min x 0.06 + 10 SMS x 0.05 = 44.00 + 3.00 + 0.50."""
    assert recommendations.rates() == {
        "data_mb": Decimal("0.05"),
        "minute": Decimal("0.06"),
        "sms": Decimal("0.05"),
    }
    cost = recommendations.overage(Usage(6000, 150, 60), Included(5120, 100, 50))
    assert cost == Decimal("47.50")
    assert recommendations.overage(Usage(6000, 150, 60), Included(6000, 150, 60)) == 0
    assert recommendations.overage(Usage(99999, 9999, 999), Included(None, None, None)) == 0


def test_projected_cost_of_another_plan_by_hand(people):
    """The roamer on DigiMax 5GB: 12.00 fee + 880 MB x 0.05 + 40 min x 0.06 + 40.00 roaming."""
    profile = services.profile(people[ROAMER])
    plans = {c.target_id: c for c in recommendations._tariff_plans(profile, Decimal("58.00"), ())}
    assert (
        plans["digimax-5"].projected == Decimal("12.00") + Decimal("44.00") + Decimal("2.40") + 40
    )
    assert plans["digimax-25"].projected == Decimal(
        "70.00"
    )  # 30.00 fee, nothing over, 40.00 roaming
    assert "digimax-10" not in plans  # the plan they are on is not a candidate


def test_redesign_values_by_hand(people):
    """13,000 MB: 751 messaging (allowance), Instagram capped at 5 GB, YouTube 2, TikTok 1.

    What is left, 4,492 MB, needs 5 GB of general internet: 13 GB in all
    against the 16 the base price covers, so 19.10 - 3 x 0.50 = 17.60.
    """
    values = recommendations.redesign_values(services.profile(people[DEMO]))
    assert values == {"instagramFb": 5, "youtube": 2, "tiktok": 1, "internet": 5, "calls": 30}


# --- recommendations ----------------------------------------------------------

TOP = {
    HEAVY: ("internet_pack", "hv-20gb", "32.98", "27.00", "5.98"),
    ROAMER: ("roaming_pack", "r-2gb", "58.00", "43.00", "15.00"),
    DEMO: ("redesign", "istesen", "19.10", "17.60", "1.50"),
}


@pytest.mark.parametrize("msisdn", list(TOP))
def test_top_recommendation(people, msisdn):
    result = recommendations.recommend(people[msisdn])
    kind, target, current, projected, saving = TOP[msisdn]
    top = result.recommendations[0]
    assert (top.kind, top.target_id) == (kind, target)
    assert (top.current, top.projected, top.saving) == (
        Decimal(current),
        Decimal(projected),
        Decimal(saving),
    )
    assert not result.fits
    assert top.action["action"] == "navigate" and top.action["to"].startswith("/")
    savings = [item.saving for item in result.recommendations]
    assert savings == sorted(savings, reverse=True) and all(s > 0 for s in savings)


def test_the_heavy_user_is_told_what_the_add_ons_cost_and_which_plan_is_cheaper(people):
    first, second = recommendations.recommend(people[HEAVY]).recommendations
    assert first.evidence == (
        "5 add-on packs, 20.98 ₼",
        "Included internet ran out on day 3 of 28",
        "YouTube 62% of data",
        "23.4 GB used in 30 days, tariff includes 5 GB",
    )
    assert (second.kind, second.target_id) == ("tariff_plan", "digimax-25")
    assert (second.projected, second.saving) == (Decimal("30.00"), Decimal("2.98"))
    assert second.action["to"] == "/tariffs/digimax?plan=digimax-25"


@pytest.mark.parametrize("msisdn", [BALANCED, VOICE])
def test_no_upsell_when_the_plan_fits(people, msisdn):
    result = recommendations.recommend(people[msisdn])
    assert result.fits and result.recommendations == ()


def test_a_category_with_nothing_to_sell_is_an_insight_without_an_offer(people):
    (insight,) = recommendations.recommend(people[BALANCED]).insights
    assert (insight.category, insight.share, insight.sells) == ("games", 0.38, ())
    assert insight.text == "Games: 38% of your data"


def test_an_insight_names_what_is_sold_for_its_category(people):
    (video,) = recommendations.recommend(people[HEAVY]).insights
    assert [(s["kind"], s["target_id"]) for s in video.sells] == [
        ("social_pack", "youtube"),
        ("app_offer", "kinon"),
    ]
    (social,) = recommendations.recommend(people[DEMO]).insights
    assert [s["kind"] for s in social.sells] == ["social_pack", "social_pack", "redesign"]
    assert recommendations.recommend(people[ROAMER]).insights == ()  # no category dominates


def test_a_dearer_option_is_shown_only_when_the_internet_ran_out(catalogue):
    """8 GB on a 5 GB plan with no add-ons bought: 12.00 was paid, nothing is cheaper.

    Because the included internet ran out, the least expensive way to cover the
    usage is still shown: the plan plus Weekly 5 GB, 17.00, with a negative saving.
    """
    person = newcomer()
    for ago in range(8):
        services.record_usage(person, today() - timedelta(days=ago), data_by_app={"other": 1024})
    result = recommendations.recommend(person)
    assert result.profile.ran_out is not None
    (only,) = result.recommendations
    assert (only.kind, only.target_id) == ("internet_pack", "weekly-5gb")
    assert (only.current, only.projected, only.saving) == (
        Decimal("12.00"),
        Decimal("17.00"),
        Decimal("-5.00"),
    )


def test_without_running_out_nothing_dearer_is_proposed(catalogue):
    person = newcomer()
    for ago in range(4):
        services.record_usage(person, today() - timedelta(days=ago), data_by_app={"other": 1024})
    result = recommendations.recommend(person)
    assert result.profile.ran_out is None and result.fits


def test_a_subscriber_without_a_tariff_gets_a_plain_answer(catalogue):
    bare = client_for(Subscriber.objects.create_user("994550000000"))
    summary = bare.get("/api/usage/summary/").json()
    assert summary["totals"]["data_mb"] == 0 and summary["segment"]["key"] == "low_usage"
    body = bare.get("/api/usage/recommendations/").json()
    assert body["fits"] is True and body["recommendations"] == [] and body["offer"] is None


# --- GET endpoints ------------------------------------------------------------


def test_summary_endpoint(people):
    body = client_for(people[HEAVY]).get("/api/usage/summary/").json()
    assert body["window"] == {
        "days": 30,
        "from": (today() - timedelta(days=29)).isoformat(),
        "to": today().isoformat(),
    }
    assert body["segment"] == {"key": "heavy_data", "label": "Heavy internet user"}
    assert body["headline"] == "23.4 GB, 60 min. and 10 SMS in 30 days; 32.98 ₼ paid"
    assert body["totals"]["data_gb"] == "23.44"
    assert body["daily_average"] == {"data_mb": 800, "minutes": 2.0, "sms": 0.3}
    assert body["data_by_category"][0] == {
        "key": "video",
        "label": "Video",
        "data_mb": body["data_by_category"][0]["data_mb"],
        "share": 0.62,
    }
    assert body["data_by_app"][0]["category"] == "video"
    assert round(sum(row["share"] for row in body["data_by_app"]), 1) == 1.0
    assert body["data_ran_out"]["day"] == 3
    assert body["spend"] == {
        "tariff_fee": "12.00",
        "addon_packs": {"count": 5, "amount": "20.98"},
        "roaming": {"count": 0, "amount": "0.00"},
        "other": "0.00",
        "total": "32.98",
    }


def test_summary_days_parameter(people):
    client = client_for(people[BALANCED])
    assert client.get("/api/usage/summary/?days=7").json()["window"]["days"] == 7
    assert client.get("/api/usage/summary/").json()["services"] == [
        {"id": "missed-call", "name": "Buraxılmış zəng"}
    ]
    for bad in ("0", "91", "abc", "-3"):
        assert client.get(f"/api/usage/summary/?days={bad}").status_code == 400, bad


def test_recommendations_endpoint(people):
    body = client_for(people[HEAVY]).get("/api/usage/recommendations/").json()
    assert body["fits"] is False and body["current_monthly_cost"] == "32.98"
    assert body["message"] == (
        "You paid 32.98 ₼ in the last 30 days; with High-volume 20 GB it would have been 27.00 ₼"
    )
    top = body["recommendations"][0]
    assert set(top) == {
        "kind", "target_id", "title", "current_monthly_cost", "projected_monthly_cost",
        "saving", "evidence", "action",
    }  # fmt: skip
    assert top["saving"] == "5.98" and len(top["evidence"]) == 4
    assert top["action"] == {
        "action": "navigate",
        "to": "/internet-packs",
        "label": "Open internet packs",
    }
    assert body["offer"] is None


def test_recommendations_endpoint_when_the_plan_fits(people):
    body = client_for(people[BALANCED]).get("/api/usage/recommendations/").json()
    assert body["fits"] is True and body["recommendations"] == []
    assert body["message"] == "Your current plan fits how you use your number"
    assert body["insights"][0]["sells"] == []


def test_recommendation_extras_by_kind(people):
    redesign = client_for(people[DEMO]).get("/api/usage/recommendations/").json()
    assert redesign["recommendations"][0]["values"]["instagramFb"] == 5
    assert redesign["recommendations"][0]["action"]["to"] == "/my-tariff/redesign"
    roaming = client_for(people[ROAMER]).get("/api/usage/recommendations/").json()
    assert "quantity" not in roaming["recommendations"][0]  # one pack is enough


@pytest.mark.parametrize(
    "language,label,evidence",
    [
        ("az", "İnternetdən çox istifadə edən", "5 əlavə paket, 20.98 ₼"),
        ("ru", "Активный пользователь интернета", "Дополнительных пакетов: 5, 20.98 ₼"),
    ],
)
def test_usage_copy_is_translated(people, language, label, evidence):
    client = client_for(people[HEAVY])
    headers = {"HTTP_ACCEPT_LANGUAGE": language}
    assert client.get("/api/usage/summary/", **headers).json()["segment"]["label"] == label
    body = client.get("/api/usage/recommendations/", **headers).json()
    assert body["recommendations"][0]["evidence"][0] == evidence
    assert body["segment"]["key"] == "heavy_data"  # keys never change


# --- the open offer -----------------------------------------------------------


def test_the_open_offer_comes_with_the_recommendations_and_is_marked_shown(client, subscriber):
    assert PersonalOffer.objects.get(id=DEMO_OFFER_ID).status == "new"
    offer = client.get("/api/usage/recommendations/").json()["offer"]
    assert offer == {
        "id": DEMO_OFFER_ID,
        "kind": "social_pack",
        "target_id": "instagram-facebook:5gb",
        "title": "Instagram & Facebook 5 GB",
        "normal_price": "3.00",
        "offer_price": "2.00",
        "reason": "Instagram & Facebook is most of your internet: 5 GB for less",
        "status": "shown",
        "expires_at": offer["expires_at"],
        "action": {
            "action": "navigate",
            "to": f"/offers/{DEMO_OFFER_ID}",
            "label": "See the offer",
        },
    }
    assert PersonalOffer.objects.get(id=DEMO_OFFER_ID).status == "shown"


def test_accepting_buys_at_the_offer_price(client, subscriber):
    response = client.pay(ACCEPT)
    assert response.status_code == 201
    body = response.json()
    assert body["offer"]["status"] == "accepted"
    assert body["transaction"] == {
        "id": body["transaction"]["id"],
        "title": "Instagram & Facebook 5 GB",
        "amount": "-2.00",  # not the normal 3.00
    }
    assert body["balance"] == "14.21"
    assert body["activation"]["pack_id"] == "instagram-facebook"
    assert body["activation"]["label"] == "Instagram & Facebook 5 GB"

    activation = PackActivation.objects.get(subscriber=subscriber)
    assert (activation.kind, activation.status) == ("social", "active")
    assert PersonalOffer.objects.get(id=DEMO_OFFER_ID).activation == activation
    # it counts as an add-on pack from now on, like any other purchase
    assert services.profile(subscriber).spend.addon_amount == Decimal("2.00")


def test_accepting_twice_with_the_same_key_charges_once(client, subscriber):
    key = str(uuid.uuid4())
    first, second = client.pay(ACCEPT, key=key), client.pay(ACCEPT, key=key)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert Wallet.objects.get(subscriber=subscriber).balance == Decimal("14.21")
    assert Transaction.objects.filter(subscriber=subscriber, amount__lt=0).count() == 1
    assert PackActivation.objects.filter(subscriber=subscriber).count() == 1


def test_accepting_again_with_a_new_key_is_refused(client, subscriber):
    assert client.pay(ACCEPT).status_code == 201
    again = client.pay(ACCEPT)
    assert again.status_code == 409
    assert again.json() == {"code": "offer_closed", "detail": "This offer is no longer available"}
    assert Wallet.objects.get(subscriber=subscriber).balance == Decimal("14.21")


def test_accepting_needs_an_idempotency_key(client):
    assert client.post_json(ACCEPT).status_code == 400
    assert PersonalOffer.objects.get(id=DEMO_OFFER_ID).status == "new"


def test_accepting_without_enough_balance_is_402_and_keeps_the_offer_open(client, subscriber):
    Wallet.objects.filter(subscriber=subscriber).update(balance=Decimal("1.99"))
    response = client.pay(ACCEPT)
    assert response.status_code == 402
    assert response.json()["code"] == "insufficient_balance"
    assert PersonalOffer.objects.get(id=DEMO_OFFER_ID).status == "new"
    assert not PackActivation.objects.filter(subscriber=subscriber).exists()
    # after a top-up the same offer still works
    Wallet.objects.filter(subscriber=subscriber).update(balance=Decimal("2.00"))
    assert client.pay(ACCEPT).json()["balance"] == "0.00"


def test_declining_closes_the_offer(client, subscriber):
    response = client.post_json(DECLINE)
    assert response.status_code == 200 and response.json()["offer"]["status"] == "declined"
    assert client.post_json(DECLINE).status_code == 409
    assert client.pay(ACCEPT).status_code == 409
    assert client.get("/api/usage/recommendations/").json()["offer"] is None
    assert Wallet.objects.get(subscriber=subscriber).balance == Decimal("16.21")


def test_an_expired_offer_cannot_be_accepted(client, subscriber):
    PersonalOffer.objects.filter(id=DEMO_OFFER_ID).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    assert client.pay(ACCEPT).status_code == 409
    assert client.post_json(DECLINE).status_code == 409
    assert client.get("/api/usage/recommendations/").json()["offer"] is None
    assert PersonalOffer.objects.get(id=DEMO_OFFER_ID).status == "expired"
    assert Wallet.objects.get(subscriber=subscriber).balance == Decimal("16.21")


def test_another_subscribers_offer_is_404(client, other, other_client):
    theirs = f"/api/usage/offers/{OTHER_OFFER_ID}"
    assert client.pay(f"{theirs}/accept/").status_code == 404
    assert client.post_json(f"{theirs}/decline/").status_code == 404
    assert (
        client.pay("/api/usage/offers/999999/accept/").json()
        == client.pay(f"{theirs}/accept/").json()
    )  # a foreign id and a missing one look the same
    assert PersonalOffer.objects.get(id=OTHER_OFFER_ID).status == "new"
    assert other_client.get("/api/usage/recommendations/").json()["offer"]["id"] == OTHER_OFFER_ID
    assert other_client.pay(f"{theirs}/accept/").json()["balance"] == "97.99"


def test_a_tariff_offer_only_points_at_the_tariff(client, subscriber):
    """Switching tariff is not built, so nothing is charged or changed."""
    PersonalOffer.objects.filter(id=DEMO_OFFER_ID).update(
        target_kind="tariff_plan", target_id="digimax-25", rule=None
    )
    response = client.pay(ACCEPT)
    assert response.status_code == 200
    body = response.json()
    assert body["action"]["to"] == "/tariffs/digimax?plan=digimax-25"
    assert set(body) == {"offer", "action"}
    assert body["offer"]["status"] == "new" and body["offer"]["title"] == "DigiMax 25GB"
    assert Wallet.objects.get(subscriber=subscriber).balance == Decimal("16.21")
    assert subscriber.tariff.title == "IsteSen"


# --- rules and the scheduled task ---------------------------------------------


def open_offers(person):
    return PersonalOffer.objects.filter(subscriber=person, status__in=PersonalOffer.OPEN)


def test_rules_give_matching_subscribers_one_offer_each(people):
    assert offers.refresh() == {"created": 2, "expired": 0}
    voice = open_offers(people[VOICE]).get()
    assert (voice.target_id, voice.normal_price, voice.offer_price) == (
        "weekly-2gb",
        Decimal("3.00"),
        Decimal("1.50"),
    )
    assert open_offers(people[ROAMER]).get().target_id == "r-2gb"
    # the heavy and the balanced subscriber match no active rule
    assert not open_offers(people[HEAVY]).exists()
    assert not open_offers(people[BALANCED]).exists()
    assert voice.expires_at - voice.created_at == timedelta(days=14)
    # running again adds nothing: at most one open offer per subscriber
    assert offers.refresh() == {"created": 0, "expired": 0}


def test_a_new_offer_is_announced_in_three_languages(people):
    offers.refresh()
    offer = open_offers(people[VOICE]).get()
    note = Notification.objects.get(subscriber=people[VOICE], slug=f"offer-{offer.id}")
    assert note.title_en == "A personal offer for you"
    assert note.title_az == "Sizə xüsusi təklif" and note.title_ru.startswith("Персональное")
    assert note.body_en.startswith("Weekly 2 GB for 1.50 ₼ instead of 3.00 ₼.")
    assert "Həftəlik 2 GB" in note.body_az and "1.50 ₼" in note.body_az
    assert note.cta_en == {"label": "See the offer", "deep_link": f"/offers/{offer.id}"}
    listed = client_for(people[VOICE]).get("/api/content/notifications/").json()
    assert listed["results"][0]["cta"]["deep_link"] == f"/offers/{offer.id}"


def test_the_voice_only_offer_works_end_to_end(people):
    """The discounted first internet pack: offered, shown, bought at half price."""
    offers.refresh()
    client = client_for(people[VOICE])
    offer = client.get("/api/usage/recommendations/").json()["offer"]
    assert offer["title"] == "Weekly 2 GB" and offer["offer_price"] == "1.50"
    bought = client.pay(f"/api/usage/offers/{offer['id']}/accept/").json()
    assert bought["transaction"] == {
        "id": bought["transaction"]["id"],
        "title": "Weekly 2 GB pack",
        "amount": "-1.50",
    }
    assert bought["balance"] == "3.50"
    assert PackActivation.objects.get(subscriber=people[VOICE]).pack_id == "weekly-2gb"
    # an accepted rule is not offered to the same subscriber again
    offers.refresh(timezone.now() + timedelta(days=30))
    assert not open_offers(people[VOICE]).exists()


def test_no_new_offer_for_seven_days_after_a_decline(people):
    offers.refresh()
    declined = open_offers(people[VOICE]).get()
    offers.decline(people[VOICE], declined.id)
    now = timezone.now()
    assert offers.refresh(now + timedelta(days=6, hours=23))["created"] == 0
    assert not open_offers(people[VOICE]).exists()
    # only the voice-only subscriber is due again; the roamer's offer is still open
    assert offers.refresh(now + timedelta(days=7, minutes=1))["created"] == 1
    assert open_offers(people[VOICE]).exists()


def test_offers_expire_and_cool_down(people):
    offers.refresh()
    now = timezone.now()
    # three run out: the two made by the rules and the one seeded for the demo subscriber
    assert offers.refresh(now + timedelta(days=14, minutes=1)) == {"created": 0, "expired": 3}
    assert PersonalOffer.objects.filter(status="expired").count() == 3
    # the cooldown counts from the expiry, too
    assert offers.refresh(now + timedelta(days=20))["created"] == 0
    assert offers.refresh(now + timedelta(days=22))["created"] == 2


def test_rules_can_be_switched_and_staff_are_never_offered(people):
    from api.seeding import seed_staff

    seed_staff()
    OfferRule.objects.filter(segment="roamer").update(is_active=False)
    assert offers.refresh()["created"] == 1
    assert not PersonalOffer.objects.filter(subscriber__is_staff=True).exists()
    assert not open_offers(people[ROAMER]).exists()


def test_a_rule_whose_item_left_the_catalogue_makes_no_offer(people):
    from api.packs.models import InternetPack

    InternetPack.objects.filter(slug="weekly-2gb").update(is_active=False)
    assert offers.refresh()["created"] == 1  # only the roamer's
    assert not open_offers(people[VOICE]).exists()


def test_the_scheduled_task_runs_the_rules(people):
    from api.usage.tasks import refresh_offers

    assert refresh_offers() == {"created": 2, "expired": 0}


# --- assistant ----------------------------------------------------------------


def test_assistant_context_is_compact_json(people):
    for msisdn, person in people.items():
        context = assistant.context(person)
        encoded = json.dumps(context, ensure_ascii=False)
        assert len(encoded) < 4500, f"{msisdn}: {len(encoded)} characters"  # about 1,500 tokens
        assert context["segment"] == PROFILES[msisdn]["segment"]
    heavy = assistant.context(people[HEAVY])
    assert heavy["plan_fits"] is False and heavy["current_monthly_cost"] == "32.98"
    assert heavy["recommendations"][0] == {
        "kind": "internet_pack",
        "target_id": "hv-20gb",
        "title": "High-volume 20 GB",
        "projected_monthly_cost": "27.00",
        "saving": "5.98",
        "evidence": heavy["recommendations"][0]["evidence"],
        "navigate_to": "/internet-packs",
    }
    assert heavy["usage"]["top_apps"][0] == {"app": "YouTube", "share": 0.62}
    assert heavy["usage"]["data_ran_out_on_day"] == 3
    assert assistant.context(people[DEMO])["offer"]["offer_price"] == "2.00"


def test_the_responder_answers_from_the_top_recommendation(people):
    reply = responder.respond(people[HEAVY], "Which tariff suits me?")
    assert reply.route == "recommendation"
    assert reply.text == (
        "In the last 30 days you paid 32.98 ₼. With High-volume 20 GB it would have been "
        "27.00 ₼, which is 5.98 ₼ less. Why: 5 add-on packs, 20.98 ₼; Included internet ran "
        "out on day 3 of 28; YouTube 62% of data; 23.4 GB used in 30 days, tariff includes 5 GB."
    )
    assert reply.action == {
        "action": "navigate",
        "to": "/internet-packs",
        "label": "Open internet packs",
    }


def test_the_responder_does_not_invent_an_upsell(people):
    reply = responder.respond(people[BALANCED], "Can you recommend a cheaper tariff?")
    assert reply.text.startswith("Your current plan fits how you use your number: you paid 18.00 ₼")
    assert reply.action is None


def test_the_responder_mentions_the_open_offer(people):
    offers.refresh()
    reply = responder.respond(people[VOICE], "Mənə hansı paket uyğundur?")
    assert "Weekly 2 GB for 1.50 ₼ instead of 3.00 ₼" in reply.text
    assert reply.action["to"].startswith("/offers/")


def test_the_recommendation_route_through_the_api(people):
    client = client_for(people[ROAMER])
    conversation = client.post_json("/api/assistant/conversations/").json()["id"]
    response = client.post(
        f"/api/assistant/conversations/{conversation}/messages/",
        {"content": "Какой тариф мне подходит?"},
        format="json",
        HTTP_ACCEPT="application/json",
    )
    body = response.json()
    assert body["message"]["route"] == "recommendation"
    assert (
        "With Roaming 2 GB it would have been 43.00 ₼, which is 15.00 ₼ less"
        in (body["message"]["content"])
    )
    assert body["action"]["to"] == "/sim/roaming"
