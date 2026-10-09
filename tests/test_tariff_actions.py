"""Paying for a tariff: subscribe, change, renew and the redesign that a renewal applies."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from api.billing.models import Transaction, Wallet
from api.packs.models import PackActivation
from api.tariffs.models import ChangeCard, SubscriberTariff, TariffPlan

SUBSCRIBE = "/api/tariffs/subscribe/"
CHANGE = "/api/tariffs/change/"
RENEW = "/api/tariffs/my/renew/"
REDESIGN = "/api/tariffs/my/redesign/"
VALUES = {"internet": 10, "calls": 100, "instagramFb": 5, "youtube": 2, "tiktok": 0}


def fund(subscriber, amount):
    Wallet.objects.filter(subscriber=subscriber).update(balance=Decimal(amount))


def balance(client):
    return client.get("/api/billing/balance/").json()["balance"]


def usage_of(client):
    return {row["kind"]: row for row in client.get("/api/tariffs/my/").json()["usage"]}


# --- subscribe ----------------------------------------------------------------


def test_subscribe_charges_and_replaces_the_tariff(client, subscriber):
    before = timezone.now()
    response = client.pay(SUBSCRIBE, {"plan_id": "digimax-5"})
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["tariff"]["family"] == "digimax"
    assert body["tariff"]["plan_id"] == "digimax-5"
    assert body["tariff"]["title"] == "DigiMax 5GB"
    assert body["tariff"]["price"] == "12.00"
    assert body["tariff"]["validity_days"] == 28
    assert body["transaction"]["title"] == "DigiMax 5GB tariff"
    assert body["transaction"]["amount"] == "-12.00"
    assert body["balance"] == "4.21" == balance(client)

    mine = client.get("/api/tariffs/my/").json()
    assert (mine["family"], mine["title"]) == ("digimax", "DigiMax 5GB")
    assert mine["lines"] == [
        {"label": "Current tariff", "value": "12.00 ₼/month"},
        {"label": "Next renewal", "value": "12.00 ₼/month"},
    ]
    usage = usage_of(client)
    assert (usage["internet"]["remaining"], usage["internet"]["total"]) == ("5.00", "5")
    assert usage["internet"]["ratio"] == 1
    assert (usage["calls"]["remaining"], usage["calls"]["total"]) == ("100", "100")
    assert usage["messaging"]["remaining"] == "1024"

    tariff = SubscriberTariff.objects.get(subscriber=subscriber)
    assert tariff.activated_at >= before and tariff.last_payment_at == tariff.activated_at
    assert tariff.next_payment_at - tariff.last_payment_at == timedelta(days=28)
    left = client.get("/api/tariffs/my/usage/").json()["period_left"]
    assert left["days"] == 27


def test_the_purchase_is_in_the_history_once(client, subscriber):
    key = str(uuid.uuid4())
    first = client.pay(SUBSCRIBE, {"plan_id": "digimax-5"}, key=key)
    again = client.pay(SUBSCRIBE, {"plan_id": "digimax-5"}, key=key)
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    assert (
        Transaction.objects.filter(subscriber=subscriber, title="DigiMax 5GB tariff").count() == 1
    )
    assert balance(client) == "4.21"


def test_not_enough_balance_changes_nothing(client, subscriber):
    response = client.pay(SUBSCRIBE, {"plan_id": "digimax-25"})  # 30.00 against 16.21
    assert response.status_code == 402
    assert response.json() == {
        "code": "insufficient_balance",
        "detail": "Not enough balance for this tariff",
    }
    assert balance(client) == "16.21"
    assert client.get("/api/tariffs/my/").json()["title"] == "IsteSen"


def test_subscribe_refuses_what_it_cannot_do(client, subscriber):
    assert client.post_json(SUBSCRIBE, {"plan_id": "digimax-5"}).status_code == 400  # no key
    assert client.pay(SUBSCRIBE, {}).status_code == 400
    unknown = client.pay(SUBSCRIBE, {"plan_id": "nope"})
    assert (unknown.status_code, unknown.json()["detail"]) == (400, "Unknown plan")

    TariffPlan.objects.filter(slug="digimax-10").update(is_active=False)
    assert client.pay(SUBSCRIBE, {"plan_id": "digimax-10"}).status_code == 400

    assert client.pay(SUBSCRIBE, {"plan_id": "digimax-5"}).status_code == 201
    same = client.pay(SUBSCRIBE, {"plan_id": "digimax-5"})
    assert same.status_code == 409
    assert same.json() == {"code": "already_active", "detail": "You are already on this tariff"}
    assert balance(client) == "4.21"


def test_unlimited_calls_have_a_number_to_show(client, subscriber):
    fund(subscriber, "100.00")
    assert client.pay(SUBSCRIBE, {"plan_id": "premium-60"}).status_code == 201
    usage = usage_of(client)
    assert usage["internet"]["total"] == "60"
    assert usage["calls"]["total"] == str(30 * 24 * 60)  # every minute of the 30 days
    assert client.get("/api/tariffs/my/").json()["payment_details"][0]["value"] == "30 d."


def test_someone_elses_tariff_is_untouched(client, other, other_client):
    assert client.pay(SUBSCRIBE, {"plan_id": "digimax-5"}).status_code == 201
    assert other_client.get("/api/tariffs/my/").json()["title"] == "IsteSen"
    assert balance(other_client) == "99.99"


# --- change -------------------------------------------------------------------


def test_change_to_a_card_without_a_page(client, subscriber):
    response = client.pay(CHANGE, {"tariff_id": "digimax-3gb"})
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["tariff"]["plan_id"] == "digimax-3gb"
    assert body["tariff"]["title"] == "DigiMax 3GB"
    assert body["transaction"]["amount"] == "-9.00"
    assert body["balance"] == "7.21"
    usage = usage_of(client)
    assert (usage["internet"]["total"], usage["calls"]["total"]) == ("3", "50")
    # the card's price is what the next period costs
    assert client.get("/api/tariffs/my/").json()["lines"][1]["value"] == "9.00 ₼/month"
    assert client.pay(CHANGE, {"tariff_id": "digimax-3gb"}).status_code == 409


def test_change_refuses_cards_it_cannot_sell(client, subscriber):
    with_page = client.pay(CHANGE, {"tariff_id": "digimax"})
    assert with_page.status_code == 400
    assert with_page.json()["detail"] == "This tariff has plans: choose one on its page"
    assert client.pay(CHANGE, {"tariff_id": "nope"}).json()["detail"] == "Unknown tariff"
    assert client.pay(CHANGE, {"tariff_id": "premium"}).status_code == 402  # 45.00

    ChangeCard.objects.filter(slug="digimax-3gb").update(data_mb=None)
    unsellable = client.pay(CHANGE, {"tariff_id": "digimax-3gb"})
    assert unsellable.status_code == 400
    assert unsellable.json()["detail"] == "This tariff cannot be chosen in the app yet"
    assert balance(client) == "16.21"


# --- renew --------------------------------------------------------------------


def test_renew_needs_the_money(client, subscriber):
    response = client.pay(RENEW)
    assert response.status_code == 402  # 19.10 against 16.21
    assert usage_of(client)["internet"]["remaining"] == "7.20"


def test_renew_refills_and_moves_the_dates(client, subscriber):
    fund(subscriber, "50.00")
    activated = SubscriberTariff.objects.get(subscriber=subscriber).activated_at
    response = client.pay(RENEW)
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["tariff"]["plan_id"] is None and body["tariff"]["title"] == "IsteSen"
    assert body["transaction"] == {
        "id": body["transaction"]["id"],
        "title": "IsteSen tariff renewal",
        "amount": "-19.10",
    }
    assert body["balance"] == "30.90"

    usage = usage_of(client)
    assert (usage["internet"]["remaining"], usage["internet"]["ratio"]) == ("16.00", 1)
    assert usage["messaging"]["remaining"] == "1024"
    tariff = SubscriberTariff.objects.get(subscriber=subscriber)
    assert tariff.activated_at == activated  # the same tariff, a new period
    assert tariff.next_payment_at - tariff.last_payment_at == timedelta(days=30)
    assert client.pay(RENEW).status_code == 201  # renewing again is allowed and charged
    assert balance(client) == "11.80"


def test_a_plan_renews_at_its_catalogue_price(client, subscriber):
    fund(subscriber, "50.00")
    client.pay(SUBSCRIBE, {"plan_id": "digimax-5"})
    SubscriberTariff.objects.filter(subscriber=subscriber).update(
        data_remaining_gb=1, minutes_remaining=3
    )
    TariffPlan.objects.filter(slug="digimax-5").update(price="13.00")
    body = client.pay(RENEW).json()
    assert body["transaction"]["amount"] == "-13.00"
    assert body["tariff"]["price"] == "13.00"
    usage = usage_of(client)
    assert (usage["internet"]["remaining"], usage["calls"]["remaining"]) == ("5.00", "100")


def test_no_tariff_no_renewal(client, subscriber):
    SubscriberTariff.objects.filter(subscriber=subscriber).delete()
    assert client.pay(RENEW).status_code == 404
    assert client.pay(SUBSCRIBE, {"plan_id": "digimax-5"}).status_code == 201  # a first tariff


# --- redesign -----------------------------------------------------------------


def test_redesign_is_saved_and_shown_again(client, subscriber):
    response = client.post_json(REDESIGN, {"values": VALUES})
    assert response.status_code == 200, response.content
    body = response.json()
    assert {slider["key"]: slider["value"] for slider in body["sliders"]} == VALUES
    # 19.10 + 0.50 × (10 − 16 + 5 + 2) + 0.02 × (100 − 30)
    assert body["estimate"] == "21.00"
    assert client.get(REDESIGN).json() == body
    assert balance(client) == "16.21"  # saving costs nothing

    mine = client.get("/api/tariffs/my/").json()
    assert mine["lines"] == [
        {"label": "Current tariff", "value": "19.10 ₼/month"},
        {"label": "Next renewal", "value": "21.00 ₼/month"},
    ]
    assert usage_of(client)["internet"]["total"] == "16"  # until the renewal


def test_a_renewal_applies_the_redesign(client, subscriber):
    fund(subscriber, "50.00")
    client.post_json(REDESIGN, {"values": VALUES})
    body = client.pay(RENEW).json()
    assert body["transaction"]["amount"] == "-21.00"
    assert body["tariff"]["price"] == "21.00"
    usage = usage_of(client)
    assert (usage["internet"]["remaining"], usage["internet"]["total"]) == ("10.00", "10")
    assert (usage["calls"]["remaining"], usage["calls"]["total"]) == ("100", "100")
    assert client.get("/api/tariffs/my/").json()["lines"][0]["value"] == "21.00 ₼/month"


def test_a_tariff_without_internet_still_renders(client, subscriber):
    fund(subscriber, "50.00")
    client.post_json(REDESIGN, {"values": {**VALUES, "internet": 0}})
    assert client.pay(RENEW).status_code == 201
    internet = usage_of(client)["internet"]
    assert (internet["total"], internet["ratio"]) == ("0", 0)
    assert client.get("/api/tariffs/my/usage/").status_code == 200


@pytest.mark.parametrize(
    "values,field",
    [
        ({**VALUES, "internet": 17}, "internet"),  # above max
        ({**VALUES, "calls": 20}, "calls"),  # below min
        ({**VALUES, "calls": 105}, "calls"),  # off the step of 10
        ({**VALUES, "extra": 1}, "extra"),
        ({key: value for key, value in VALUES.items() if key != "tiktok"}, "tiktok"),
    ],
)
def test_redesign_rejects_values_the_sliders_do_not_allow(client, subscriber, values, field):
    response = client.post_json(REDESIGN, {"values": values})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation_error"
    assert list(body["errors"]["values"]) == [field]
    assert client.get(REDESIGN).json()["estimate"] == "19.10"


def test_redesign_input_must_be_whole_numbers(client, subscriber):
    for values in ("x", {"internet": "a lot"}, {"internet": 1.5}, None):
        assert client.post_json(REDESIGN, {"values": values}).status_code == 400
    assert client.post_json(REDESIGN, {}).status_code == 400


def test_only_istesen_is_redesigned(client, subscriber):
    client.pay(SUBSCRIBE, {"plan_id": "digimax-5"})
    response = client.post_json(REDESIGN, {"values": VALUES})
    assert response.status_code == 400
    assert response.json()["detail"] == "Only the IsteSen tariff can be redesigned"


# --- the aggregated total -----------------------------------------------------


def test_active_internet_packs_are_added_to_the_total(client, subscriber):
    remaining = client.get("/api/tariffs/my/usage/").json()["remaining"]
    assert (remaining["data_gb"], remaining["data_total_gb"]) == ("7.20", "16")

    client.pay("/api/packs/internet/purchase/", {"pack_id": "weekly-5gb"})
    client.pay("/api/packs/internet/purchase/", {"pack_id": "daily-500mb"})
    client.pay("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"})  # no size to add
    body = client.get("/api/tariffs/my/usage/").json()
    assert body["remaining"]["data_gb"] == "12.69"  # 7.20 + 5 + 500/1024
    assert body["remaining"]["data_total_gb"] == "21.49"
    assert body["rows"][0]["total"] == "16"  # the rows are the tariff alone

    PackActivation.objects.filter(subscriber=subscriber).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    remaining = client.get("/api/tariffs/my/usage/").json()["remaining"]
    assert (remaining["data_gb"], remaining["data_total_gb"]) == ("7.20", "16")


def test_messages_are_translated(client, subscriber):
    answer = client.post_json(
        SUBSCRIBE,
        {"plan_id": "digimax-25"},
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        HTTP_ACCEPT_LANGUAGE="az",
    )
    assert answer.json()["detail"] == "Bu tarif üçün balans kifayət etmir"
