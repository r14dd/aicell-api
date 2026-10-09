"""tariffs, packs, kredit, referral."""

import pytest

from api.tariffs.models import SubscriberTariff, TariffFamily

# --- tariffs ----------------------------------------------------------------


def test_catalogue_family_selects_the_plan(client):
    body = client.get("/api/tariffs/catalogue/digimax/?plan=digimax-25").json()
    assert body["selected_plan"] == "digimax-25"
    assert body["cta"] == "Subscribe for 30.00 ₼"
    assert [plan["id"] for plan in body["plans"]] == ["digimax-5", "digimax-10", "digimax-25"]
    assert [group["tone"] for group in body["total_price"]] == ["secondary", "red"]
    assert "default_plan" not in body

    assert client.get("/api/tariffs/catalogue/digimax/?plan=nope").status_code == 400
    assert client.get("/api/tariffs/catalogue/nope/").status_code == 404
    assert len(client.get("/api/tariffs/catalogue/").json()["results"]) == 2


def test_hot_tariffs_are_in_frame_order(client):
    ids = [card["id"] for card in client.get("/api/tariffs/hot/").json()["results"]]
    assert ids == ["digimax-10", "premium-60", "digimax-25"]


def test_my_tariff(client):
    body = client.get("/api/tariffs/my/").json()
    assert body["title"] == "IsteSen"
    assert body["pills"] == ["CURRENT TARIFF", "PREPAID"]
    assert body["lines"][0] == {"label": "Current tariff", "value": "19.10 ₼/month"}
    assert body["usage"] == [
        {
            "kind": "internet",
            "label": "Internet",
            "remaining": "7.20",
            "remaining_unit": "GB",
            "total": "16",
            "total_unit": "GB",
            "ratio": 0.45,
        },
        {
            "kind": "messaging",
            "label": "Messaging",
            "remaining": "1003",
            "remaining_unit": "MB",
            "total": "1",
            "total_unit": "GB",
            "ratio": 0.98,
        },
        {
            "kind": "calls",
            "label": "Local calls",
            "remaining": "30",
            "remaining_unit": "MIN.",
            "total": "30",
            "total_unit": "MIN.",
            "ratio": 1,
        },
    ]
    details = {row["label"]: row["value"] for row in body["payment_details"]}
    assert details == {
        "Validity period": "30 d.",
        "Activation date": "2026-09-24T00:00:00+04:00",
        "Last payment date": "2026-09-24T00:00:00+04:00",
        "Next payment date": "2026-10-25T08:00:00+04:00",
        "Payment amount": "19.10",
    }
    assert [len(group["rows"]) for group in body["total_price"]] == [4, 4]


def test_my_usage(client):
    body = client.get("/api/tariffs/my/usage/").json()
    assert body["tariff"] == "IsteSen"
    assert body["renewal_label"].startswith("Renews 25 October")
    assert body["remaining"]["data_gb"] == "7.20"
    assert body["remaining"]["minutes"] == 30
    assert set(body["period_left"]) == {"days", "hours"}
    assert len(body["rows"]) == 3 and len(body["aggregation"]) == 2


def test_redesign_defaults_estimate_the_base_price(client):
    body = client.get("/api/tariffs/my/redesign/").json()
    assert [s["key"] for s in body["sliders"]] == [
        "internet",
        "calls",
        "instagramFb",
        "youtube",
        "tiktok",
    ]
    assert body["sliders"][1] == {
        "key": "calls",
        "label": "Local calls min.",
        "min": 30,
        "max": 350,
        "step": 10,
        "value": 30,
    }
    assert body["pricing"] == {"base": "19.10", "per_gb": "0.50", "per_minute": "0.02"}
    assert body["estimate"] == "19.10"


@pytest.mark.parametrize(
    "field, kind",
    [
        ("data_total_gb", "internet"),
        ("messaging_total_gb", "messaging"),
        ("minutes_total", "calls"),
    ],
)
def test_a_zero_total_gives_a_zero_ratio(client, subscriber, field, kind):
    SubscriberTariff.objects.filter(subscriber=subscriber).update(**{field: 0})
    usage = {row["kind"]: row for row in client.get("/api/tariffs/my/").json()["usage"]}
    assert usage[kind]["ratio"] == 0
    assert client.get("/api/tariffs/my/usage/").status_code == 200


def test_a_partial_redesign_estimates_from_the_included_amounts(client, subscriber):
    SubscriberTariff.objects.filter(subscriber=subscriber).update(redesign={"internet": 20})
    assert client.get("/api/tariffs/my/").status_code == 200
    assert client.get("/api/tariffs/my/redesign/").json()["estimate"] == "21.10"


def test_a_family_without_plans_is_left_out_of_the_catalogue(client):
    TariffFamily.objects.create(slug="empty", name="Empty")
    assert len(client.get("/api/tariffs/catalogue/").json()["results"]) == 2
    assert client.get("/api/tariffs/catalogue/empty/").status_code == 404


def test_change_and_premium(client):
    groups = client.get("/api/tariffs/change/").json()["results"]
    assert [group["id"] for group in groups] == ["digimax", "premium"]
    family_ids = [card["family_id"] for group in groups for card in group["cards"]]
    assert family_ids == ["digimax", None, "premium-plus", None]

    premium = client.get("/api/tariffs/premium/").json()
    assert len(premium["benefits"]) == 8
    assert premium["logo"].startswith("http")


# --- packs ------------------------------------------------------------------


def test_internet_page(client):
    body = client.get("/api/packs/internet/").json()
    assert [c["id"] for c in body["categories"]] == [
        "unlimited",
        "high-volume",
        "weekly",
        "daily",
        "social",
    ]
    assert set(body["packs"]) == {"unlimited", "high-volume", "weekly", "daily"}
    assert body["packs"]["unlimited"][0] == {
        "id": "unlimited-1h",
        "name": "1 hour",
        "sub": "Unlimited speed",
        "price": "0.99",
        "renews": False,
        "label": "Unlimited 1 hour",
    }
    assert [card["id"] for card in body["social"]] == [
        "tehsil",
        "instagram-facebook",
        "tiktok",
        "youtube",
    ]
    assert "plans" not in body["social"][0]
    assert body["msisdn"] == "994516643342"
    assert len(client.get("/api/packs/internet/top/").json()["results"]) == 3


def test_internet_purchase(client):
    response = client.pay("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"})
    assert response.status_code == 201
    body = response.json()
    assert body["activation"]["pack_id"] == "unlimited-1h"
    assert body["activation"]["label"] == "Unlimited 1 hour"
    assert body["activation"]["status"] == "active"
    assert body["activation"]["auto_renew"] is False
    assert body["activation"]["expires_at"] > body["activation"]["activated_at"]
    assert body["transaction"]["title"] == "Unlimited 1 hour pack"
    assert body["transaction"]["amount"] == "-0.99"
    assert body["balance"] == "15.22"

    newest = client.get("/api/billing/transactions/").json()["results"][0]
    assert newest["kind"] == "purchase" and newest["title"] == "Unlimited 1 hour pack"


def test_internet_purchase_errors(client):
    poor = client.pay("/api/packs/internet/purchase/", {"pack_id": "hv-100gb"})
    assert poor.status_code == 402
    assert poor.json() == {
        "code": "insufficient_balance",
        "detail": "Not enough balance for this pack",
    }
    assert client.pay("/api/packs/internet/purchase/", {"pack_id": "nope"}).status_code == 400
    assert client.get("/api/billing/balance/").json()["balance"] == "16.21"


def test_social_detail_and_activation(client):
    detail = client.get("/api/packs/social/tehsil/").json()
    assert detail["badge"] == "AUTO-RENEWAL"
    assert detail["default_plan"] == "10gb"
    assert detail["plans"][1] == {
        "id": "100gb",
        "title": "100 GB",
        "price": "9.90",
        "validity": "30 d.",
    }
    assert detail["rows"][0] == {"label": "Application traffic", "value": "10 GB"}

    response = client.pay("/api/packs/social/tehsil/activate/", {"plan_id": "100gb"})
    assert response.status_code == 201
    body = response.json()
    assert body["activation"]["label"] == "Tehsil 100 GB"
    assert body["activation"]["auto_renew"] is True
    assert body["transaction"]["title"] == "Tehsil 100 GB"
    assert body["transaction"]["amount"] == "-9.90"
    assert body["balance"] == "6.31"

    again = client.pay("/api/packs/social/tehsil/activate/", {"plan_id": "10gb"})
    assert again.status_code == 409
    assert again.json()["code"] == "already_active"
    assert client.pay("/api/packs/social/tehsil/activate/", {"plan_id": "nope"}).status_code == 400


def test_roaming_packs(client):
    body = client.get("/api/packs/roaming/").json()
    assert body["results"][1] == {"id": "r-2gb", "name": "2 GB", "sub": "10 days", "price": "25.00"}
    assert body["confirm"]["confirm"] == "Yes, activate the pack"

    assert client.pay("/api/packs/roaming/purchase/", {"pack_id": "r-2gb"}).status_code == 402
    bought = client.pay("/api/packs/roaming/purchase/", {"pack_id": "r-500mb"}).json()
    assert bought["activation"]["label"] == "Roaming 500 MB"
    assert bought["transaction"]["title"] == "Roaming 500 MB pack"
    assert bought["balance"] == "6.21"


# --- kredit -----------------------------------------------------------------


def test_kredit_overview_and_products(client):
    body = client.get("/api/kredit/").json()
    assert body["debt"] == {"amount": "0.00", "note": "no items", "items": []}
    assert [p["id"] for p in body["products"]] == [
        "simkredit",
        "simtaksit",
        "internetkredit",
        "ekstrakredit",
    ]

    taksit = client.get("/api/kredit/products/simtaksit/").json()
    assert taksit["amount"] == "2.00" and taksit["fee"] == "0.60"
    assert taksit["cta"] == "Get SimTaksit 2.00 ₼"
    assert "options" not in taksit and "amount_mb" not in taksit
    assert client.get("/api/kredit/products/simkredit/").json()["options"] == ["1", "2", "3"]
    internet = client.get("/api/kredit/products/internetkredit/").json()
    assert internet["amount_mb"] == 300 and internet["validity_days"] == 7
    assert client.get("/api/kredit/products/nope/").status_code == 404


def test_kredit_take_keeps_the_app_notice(client):
    response = client.post_json("/api/kredit/products/simtaksit/take/", {"amount": "2.00"})
    assert response.status_code == 501
    assert response.json() == {
        "code": "not_implemented",
        "detail": "SimTaksit 2.00 ₼ will be added to your balance (prototype)",
    }
    assert client.post_json("/api/kredit/products/nope/take/").status_code == 404
    assert client.get("/api/billing/balance/").json()["balance"] == "16.21"


@pytest.mark.parametrize(
    "body", [{"amount": "1e999999999"}, {"amount": "1e100000"}, {"amount": "NaN"}, [1], "x"]
)
def test_kredit_take_keeps_the_default_for_an_unusable_amount(client, body):
    response = client.post_json("/api/kredit/products/simtaksit/take/", body)
    assert response.status_code == 501
    assert response.json()["detail"] == "SimTaksit 2.00 ₼ will be added to your balance (prototype)"


def test_tamamla(client):
    body = client.get("/api/kredit/tamamla/").json()
    assert len(body["steps"]) == 3
    assert body["cta"] == {"label": "Get now!", "url": "https://links.akart.az/app/"}


# --- referral ---------------------------------------------------------------


def test_referral_me(client):
    body = client.get("/api/referral/me/").json()
    assert body["code"] == "wa16Kg"
    assert body["share_url"] == "https://azercell.com/app?ref=wa16Kg"
    assert body["earned"] == "0.00"
    assert len(body["steps"]) == 3
    assert body["terms_url"] is None
