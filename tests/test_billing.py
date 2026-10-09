import pytest
from django.utils import timezone


def test_balance(client):
    now = timezone.localtime()
    body = client.get("/api/billing/balance/").json()
    assert body["balance"] == "16.21"
    assert body["currency"] == "AZN"
    assert body["month"] == now.strftime("%Y-%m")
    # The seeded top-ups are from October 2026.
    assert body["top_ups_this_month"] == ("16.00" if body["month"] == "2026-10" else "0.00")


def test_top_up_adds_to_this_months_sum(client):
    before = client.get("/api/billing/balance/").json()
    client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "5.00"})
    after = client.get("/api/billing/balance/").json()
    assert float(after["top_ups_this_month"]) == float(before["top_ups_this_month"]) + 5


def test_transactions_are_newest_first_and_paginated(client):
    body = client.get("/api/billing/transactions/").json()
    assert [row["amount"] for row in body["results"]] == ["15.00", "1.00"]
    assert body["results"][0] == {
        "id": body["results"][0]["id"],
        "kind": "top_up",
        "title": "Number balance",
        "amount": "15.00",
        "created_at": "2026-10-02T12:39:00Z",
    }
    assert body["next"] is None

    first = client.get("/api/billing/transactions/?limit=1").json()
    assert len(first["results"]) == 1 and first["next"]
    second = client.get(f"/api/billing/transactions/?limit=1&cursor={first['next']}").json()
    assert second["results"][0]["amount"] == "1.00"
    assert second["next"] is None


def test_top_ups_date_range_is_inclusive_in_baku_time(client):
    assert len(client.get("/api/billing/top-ups/").json()["results"]) == 2
    inside = client.get("/api/billing/top-ups/?from=2026-10-02&to=2026-10-02").json()
    assert [row["amount"] for row in inside["results"]] == ["15.00", "1.00"]
    assert client.get("/api/billing/top-ups/?from=2026-10-03&to=2026-10-06").json()["results"] == []
    assert client.get("/api/billing/top-ups/?from=nope").status_code == 400


@pytest.mark.parametrize("path", ["/api/billing/top-ups/", "/api/content/notifications/"])
@pytest.mark.parametrize("query", ["from=0001-01-01", "to=9999-12-31"])
def test_the_first_and_last_days_are_open_ends(client, path, query):
    assert client.get(f"{path}?{query}").json()["results"] == client.get(path).json()["results"]


def test_card_top_up(client):
    response = client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "25.00"})
    assert response.status_code == 201
    body = response.json()
    assert body["top_up"]["method"] == "card"
    assert body["top_up"]["amount"] == "25.00"
    assert body["top_up"]["status"] == "completed"
    assert body["transaction"]["title"] == "Number balance"
    assert body["transaction"]["amount"] == "25.00"
    assert body["balance"] == "41.21"


def test_top_up_amount_limits(client):
    for amount in ("0.99", "500.01", "abc"):
        response = client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": amount})
        assert response.status_code == 400, amount
        assert response.json()["detail"] == "Enter an amount between 1.00 and 500.00 ₼"


def test_akart_top_up_saves_the_number(client):
    data = {"akart_msisdn": "994516643342", "amount": "20.00", "save": True}
    body = client.pay("/api/billing/top-up/akart/", data).json()
    assert body["top_up"]["method"] == "akart"
    assert body["saved_akart"]["msisdn"] == "994516643342"
    assert body["balance"] == "36.21"
    bad = client.pay(
        "/api/billing/top-up/akart/", {"akart_msisdn": "0516643342", "amount": "20.00"}
    )
    assert bad.status_code == 400


def test_google_pay_simulated_token(client, settings):
    data = {"amount": "20.00", "payment_token": "simulated", "card_last4": "4471"}
    response = client.pay("/api/billing/top-up/google-pay/", data)
    assert response.status_code == 201
    assert response.json()["top_up"]["method"] == "google_pay"

    real = client.pay("/api/billing/top-up/google-pay/", {**data, "payment_token": "real-token"})
    assert real.status_code == 501
    settings.GOOGLE_PAY_SIMULATED = False
    assert client.pay("/api/billing/top-up/google-pay/", data).status_code == 501
    assert client.get("/api/billing/balance/").json()["balance"] == "36.21"


def test_cards_and_methods(client):
    cards = client.get("/api/billing/cards/").json()["results"]
    assert cards == [
        {
            "id": cards[0]["id"],
            "brand": "mastercard",
            "last4": "4471",
            "expiry": "09/28",
            "is_default": True,
        }
    ]
    methods = client.get("/api/billing/top-up/methods/").json()
    assert [m["key"] for m in methods["methods"]] == ["card", "akart", "voucher", "kredit"]
    assert methods["banner"]["image"].startswith("http")
    assert methods["google_pay"]["max"] == "500.00"


def test_steam_top_up(client):
    accounts = client.get("/api/billing/steam/accounts/").json()
    assert accounts["results"][0]["name"] == "gamer_01"
    assert accounts["limits"] == {"min": "1.00", "max": "50.00"}

    response = client.pay(
        "/api/billing/steam/top-up/", {"account": "gamer_01", "amount": "10.00", "save": True}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["steam_top_up"]["account"] == "gamer_01"
    assert body["transaction"] == {
        "id": body["transaction"]["id"],
        "title": "Steam balance gamer_01",
        "amount": "-10.00",
    }
    assert body["balance"] == "6.21"

    newest = client.get("/api/billing/transactions/").json()["results"][0]
    assert newest["kind"] == "payment" and newest["amount"] == "-10.00"


def test_steam_top_up_errors(client):
    over = client.pay("/api/billing/steam/top-up/", {"account": "gamer_01", "amount": "60.00"})
    assert over.status_code == 400
    assert over.json()["detail"] == "Enter an amount between 1.00 and 50.00 ₼"

    poor = client.pay("/api/billing/steam/top-up/", {"account": "gamer_01", "amount": "40.00"})
    assert poor.status_code == 402
    assert poor.json() == {
        "code": "insufficient_balance",
        "detail": "Not enough balance for this top-up",
    }
    assert client.get("/api/billing/balance/").json()["balance"] == "16.21"


def test_steam_save_adds_a_new_account(client):
    client.pay("/api/billing/steam/top-up/", {"account": "new_one", "amount": "5.00", "save": True})
    client.pay("/api/billing/steam/top-up/", {"account": "not_saved", "amount": "1.00"})
    names = [a["name"] for a in client.get("/api/billing/steam/accounts/").json()["results"]]
    assert "new_one" in names and "not_saved" not in names
