from datetime import date
from decimal import Decimal

import pytest

from api.billing import services as billing
from api.sim.models import ServiceSubscription, SimProfile, SimService


@pytest.fixture
def sim(subscriber):
    return SimProfile.objects.create(
        subscriber=subscriber,
        one_way_blocking_date=date(2026, 10, 25),
        deactivation_date=date(2027, 1, 23),
        puk1="12345678",
        puk2="87654321",
    )


@pytest.fixture
def service(db):
    return SimService.objects.create(
        slug="missed-call",
        name="Missed call",
        sub="Know who called",
        period="monthly",
        days=30,
        price=Decimal("1.50"),
        sections=[{"text": "Info"}, {"option": {"id": "extra", "label": "Extra"}}],
    )


def test_overview_and_line(client, sim):
    body = client.get("/api/sim/").json()
    assert body["badge"] == "4G (LTE) enabled"
    assert body["details"][0]["value"] == "2026-10-25"
    assert client.get("/api/sim/line/").json()["status_title"] == "Line status: Open"
    updated = client.patch_json("/api/sim/line/", {"mobile_internet": False}).json()
    assert updated["mobile_internet"] is False
    assert client.patch_json("/api/sim/line/", {"mobile_internet": "maybe"}).status_code == 400


def test_call_forwarding_all_wins(client, sim):
    url = "/api/sim/call-forwarding/"
    assert client.patch_json(url, {"busy": True}).json()["busy"] is True
    assert client.patch_json(url, {"all": True}).json()["busy"] is False
    rejected = client.patch_json(url, {"unreachable": True})
    assert rejected.status_code == 400 and rejected.json()["code"] == "validation_error"
    assert client.patch_json(url, {"all": False, "busy": True}).json()["busy"] is True


def test_roaming_and_puk(client, sim):
    assert client.get("/api/sim/roaming/").json()["changed_at"] is None
    assert client.patch_json("/api/sim/roaming/", {"enabled": True}).json()["changed_at"]
    assert client.get("/api/sim/puk/").json()["codes"][0]["value"] == "1234 5678"


def test_no_sim_is_404(client):
    assert client.get("/api/sim/").status_code == 404


def test_subscribe_charges_once(client, subscriber, service):
    billing.top_up(subscriber, "card", Decimal("5.00"))
    assert client.get("/api/sim/services/").json()["results"][0]["price"] == "1.50"
    res = client.pay("/api/sim/services/missed-call/subscribe/", {"options": ["extra"]})
    assert res.status_code == 201
    assert res.json()["balance"] == "3.50"
    assert ServiceSubscription.objects.filter(subscriber=subscriber).count() == 1
    again = client.pay("/api/sim/services/missed-call/subscribe/")
    assert again.status_code == 409
    row = client.get("/api/sim/services/").json()["results"][0]
    assert row["activated"] is True and row["price"] is None


def test_subscribe_errors(client, subscriber, service):
    assert client.pay("/api/sim/services/missed-call/subscribe/").status_code == 402
    billing.top_up(subscriber, "card", Decimal("5.00"))
    assert (
        client.pay("/api/sim/services/missed-call/subscribe/", {"options": ["x"]}).status_code
        == 400
    )
    assert client.pay("/api/sim/services/nope/subscribe/").status_code == 404
