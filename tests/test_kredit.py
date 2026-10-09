from decimal import Decimal

import pytest

from api.kredit.models import CreditDebt, KreditProduct


@pytest.fixture
def products(db):
    KreditProduct.objects.create(
        slug="simtaksit",
        name="Simtaksit",
        subtitle="Pay in parts",
        chip="Popular",
        chip_icon="star",
        price_label="2 ₼",
        amount=Decimal("10"),
        fee=Decimal("2"),
        options=[5, 10],
    )
    KreditProduct.objects.create(
        slug="data",
        name="Data",
        subtitle="Extra data",
        chip="New",
        chip_icon="wifi",
        amount=Decimal("1"),
        amount_mb=500,
        validity_days=3,
    )


def test_overview_sums_open_debt(client, subscriber, products):
    CreditDebt.objects.create(
        subscriber=subscriber, product="simtaksit", name="Simtaksit", amount=10, fee=2
    )
    body = client.get("/api/kredit/").json()
    assert body["debt"]["amount"] == "12.00"
    assert body["debt"]["note"] == "1 items"
    assert [card["id"] for card in body["products"]] == ["simtaksit", "data"]
    assert body["products"][0]["deep_link"] == "/kredit/simtaksit"


def test_product_detail_shapes(client, products):
    plain = client.get("/api/kredit/products/simtaksit/").json()
    assert plain["options"] == [5, 10] and "amount_mb" not in plain
    data = client.get("/api/kredit/products/data/").json()
    assert data["amount_mb"] == 500 and data["validity_days"] == 3
    assert client.get("/api/kredit/products/nope/").status_code == 404


def test_take_is_todo_and_echoes_amount(client, products):
    res = client.post_json("/api/kredit/products/simtaksit/take/", {"amount": "5"})
    assert res.status_code == 501
    assert "5.00" in str(res.json())
