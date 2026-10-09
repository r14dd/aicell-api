"""What the usage says to do, the lifecycle of an insight and the tariff advisor."""

from datetime import timedelta

from django.utils import timezone

from api.insights import services
from api.insights.models import Insight
from api.seeding import DEMO_INSIGHT_ID, TEST_NUMBERS, seed_test_numbers

from .conftest import client_for

HEAVY, VOICE, ROAMER, BALANCED = TEST_NUMBERS
URL = "/api/insights/"
SEEN = f"{URL}{DEMO_INSIGHT_ID}/seen/"
ACCEPT = f"{URL}{DEMO_INSIGHT_ID}/accept/"
DISMISS = f"{URL}{DEMO_INSIGHT_ID}/dismiss/"
TASKS = {"topUp", "buyPack", "changeTariff", "activatePack", "applyRedesign"}


def kinds_of(msisdn):
    person = next(p for p in seed_test_numbers() if p.msisdn == msisdn)
    return [item.kind for item in services.detect(person)]


def test_demo_gets_the_seeded_insight(client):
    body = client.get(URL).json()
    first = body["insights"][0]
    assert first["id"] == DEMO_INSIGHT_ID
    assert first["kind"] == "social_heavy"
    assert first["status"] == "new"
    assert first["offers"][0]["task"]["name"] == "applyRedesign"
    assert first["recommended"] == 0


def test_every_offer_is_a_laya_task(client):
    for item in client.get(URL).json()["insights"]:
        for offer in item["offers"]:
            assert offer["task"]["name"] in TASKS
            assert isinstance(offer["task"]["params"], dict)


def test_the_stories_trigger_their_kinds(catalogue):
    assert kinds_of(HEAVY) == ["overage", "repeat_packs", "video_heavy"]
    assert kinds_of(ROAMER) == ["roaming"]
    assert kinds_of(VOICE) == []
    assert kinds_of(BALANCED) == []


def test_listing_twice_keeps_one_row_per_kind(client, subscriber):
    client.get(URL)
    client.get(URL)
    assert Insight.objects.filter(subscriber=subscriber, kind="social_heavy").count() == 1


def test_seen_then_accept_then_closed(client):
    assert client.post_json(SEEN).json()["insight"]["status"] == "seen"
    assert client.post_json(SEEN).json()["insight"]["status"] == "seen"
    accepted = client.post_json(ACCEPT).json()["insight"]
    assert accepted["status"] == "accepted"
    assert accepted["decided_at"]
    for path in (SEEN, ACCEPT, DISMISS):
        response = client.post_json(path)
        assert response.status_code == 409
        assert response.json()["code"] == "insight_closed"


def test_a_closed_insight_stays_out_for_a_week(client):
    client.post_json(DISMISS)
    assert DEMO_INSIGHT_ID not in [i["id"] for i in client.get(URL).json()["insights"]]

    Insight.objects.filter(id=DEMO_INSIGHT_ID).update(decided_at=timezone.now() - timedelta(days=8))
    reopened = {i["id"]: i for i in client.get(URL).json()["insights"]}[DEMO_INSIGHT_ID]
    assert reopened["status"] == "new"
    assert reopened["decided_at"] is None


def test_another_subscribers_insight_is_not_found(other_client):
    for path in (SEEN, ACCEPT, DISMISS):
        assert other_client.post_json(path).status_code == 404
    assert Insight.objects.get(id=DEMO_INSIGHT_ID).status == "new"


def test_a_missing_insight_is_not_found(client):
    assert client.post_json(f"{URL}1/seen/").status_code == 404


def test_insights_need_a_login(anon):
    assert anon.get(URL).status_code == 401
    assert anon.get(f"{URL}advisor/").status_code == 401
    assert anon.post_json(SEEN).status_code == 401


def test_advisor_compares_with_cheaper_options(catalogue):
    heavy = next(p for p in seed_test_numbers() if p.msisdn == HEAVY)
    body = client_for(heavy).get(f"{URL}advisor/").json()
    assert body["current"]["monthly_cost"]
    assert body["effective_from"]
    ids = [c["id"] for c in body["candidates"]]
    assert body["recommended"] in [*ids, "current"]
    for candidate in body["candidates"]:
        assert candidate["task"]["name"] in {"changeTariff", "applyRedesign"}
        assert float(candidate["saving_month"]) > 0


def test_advisor_says_current_when_nothing_is_cheaper(catalogue):
    balanced = next(p for p in seed_test_numbers() if p.msisdn == BALANCED)
    body = client_for(balanced).get(f"{URL}advisor/").json()
    assert body["candidates"] == []
    assert body["recommended"] == "current"
