import uuid

from api.billing import services


def fund(subscriber, amount="16.21"):
    services.top_up(subscriber, "card", amount)


def test_balance_starts_empty(client):
    body = client.get("/api/billing/balance/").json()
    assert body["balance"] == "0.00"
    assert body["currency"] == "AZN"


def test_card_top_up(client):
    response = client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "25.00"})
    assert response.status_code == 201
    body = response.json()
    assert body["top_up"]["method"] == "card"
    assert body["top_up"]["status"] == "completed"
    assert body["transaction"]["amount"] == "25.00"
    assert body["balance"] == "25.00"
    assert client.get("/api/billing/balance/").json()["top_ups_this_month"] == "25.00"


def test_top_up_amount_limits(client):
    for amount in ("0.99", "500.01", "abc"):
        response = client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": amount})
        assert response.status_code == 400, amount
        assert response.json()["detail"] == "Enter an amount between 1.00 and 500.00 ₼"


def test_a_repeated_key_moves_money_once(client):
    key = str(uuid.uuid4())
    data = {"card_bin": "416300", "amount": "10.00"}
    first = client.pay("/api/billing/top-up/card/", data, key=key)
    again = client.pay("/api/billing/top-up/card/", data, key=key)
    assert again.status_code == 201 and again.json() == first.json()
    assert client.get("/api/billing/balance/").json()["balance"] == "10.00"


def test_money_post_needs_a_key(client):
    response = client.post_json("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "5"})
    assert response.status_code == 400


def test_akart_top_up_saves_the_number(client):
    data = {"akart_msisdn": "994516643342", "amount": "20.00", "save": True}
    body = client.pay("/api/billing/top-up/akart/", data).json()
    assert body["top_up"]["method"] == "akart"
    assert body["saved_akart"]["msisdn"] == "994516643342"
    bad = client.pay("/api/billing/top-up/akart/", {"akart_msisdn": "0516643342", "amount": "20"})
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


def test_steam_top_up(client, subscriber):
    fund(subscriber)
    response = client.pay(
        "/api/billing/steam/top-up/", {"account": "gamer_01", "amount": "10.00", "save": True}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["transaction"]["title"] == "Steam balance gamer_01"
    assert body["transaction"]["amount"] == "-10.00"
    assert body["balance"] == "6.21"
    accounts = client.get("/api/billing/steam/accounts/").json()
    assert [a["name"] for a in accounts["results"]] == ["gamer_01"]
    assert accounts["limits"] == {"min": "1.00", "max": "50.00"}


def test_steam_top_up_errors(client, subscriber):
    fund(subscriber)
    over = client.pay("/api/billing/steam/top-up/", {"account": "gamer_01", "amount": "60.00"})
    assert over.status_code == 400
    poor = client.pay("/api/billing/steam/top-up/", {"account": "gamer_01", "amount": "40.00"})
    assert poor.status_code == 402
    assert poor.json() == {
        "code": "insufficient_balance",
        "detail": "Not enough balance for this top-up",
    }
    assert client.get("/api/billing/balance/").json()["balance"] == "16.21"


def test_transactions_are_newest_first_and_paginated(client, subscriber):
    services.top_up(subscriber, "card", "1.00")
    services.top_up(subscriber, "card", "15.00")
    body = client.get("/api/billing/transactions/").json()
    assert [row["amount"] for row in body["results"]] == ["15.00", "1.00"]
    assert body["next"] is None
    first = client.get("/api/billing/transactions/?limit=1").json()
    assert len(first["results"]) == 1 and first["next"]
    second = client.get(f"/api/billing/transactions/?limit=1&cursor={first['next']}").json()
    assert second["results"][0]["amount"] == "1.00" and second["next"] is None


def test_top_up_history_date_range(client, subscriber):
    services.top_up(subscriber, "card", "5.00")
    assert len(client.get("/api/billing/top-ups/").json()["results"]) == 1
    assert client.get("/api/billing/top-ups/?from=2020-01-01&to=2020-01-02").json()["results"] == []
    assert client.get("/api/billing/top-ups/?from=nope").status_code == 400


def test_todo_routes_answer_501(client):
    assert client.post_json("/api/billing/top-up/voucher/").status_code == 501
    assert client.get("/api/billing/payments/").status_code == 501
