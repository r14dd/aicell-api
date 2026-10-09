def test_overview(client):
    body = client.get("/api/sim/").json()
    assert body["badge"] == "4G (LTE) enabled"
    assert body["details"] == [
        {"label": "One-way blocking", "value": "2026-10-25"},
        {"label": "Deactivation date", "value": "2027-01-23"},
    ]
    assert [row["key"] for row in body["rows"]] == [
        "line",
        "roaming",
        "esim",
        "sms",
        "puk",
        "services",
    ]


def test_line_toggles(client):
    body = client.get("/api/sim/line/").json()
    assert body["status_title"] == "Line status: Open"
    assert body["mobile_internet"] is True and body["call_forwarding_status"] == "Off"

    updated = client.patch_json("/api/sim/line/", {"mobile_internet": False}).json()
    assert updated["mobile_internet"] is False and updated["second_line"] is True
    assert client.get("/api/sim/line/").json()["mobile_internet"] is False
    assert client.patch_json("/api/sim/line/", {"mobile_internet": "maybe"}).status_code == 400


def test_line_status(client):
    body = client.get("/api/sim/line/status/").json()
    assert body["fee"] == "20.00"
    assert body["suspend_until"] == "2027-01-23"
    assert len(body["consequences"]) == 4


def test_call_forwarding_all_wins(client):
    url = "/api/sim/call-forwarding/"
    assert client.get(url).json() == {
        "all": False,
        "unanswered": False,
        "busy": False,
        "unreachable": False,
    }

    assert client.patch_json(url, {"busy": True}).json()["busy"] is True
    assert client.get("/api/sim/line/").json()["call_forwarding_status"] == "On"

    # all=true resets the other three
    assert client.patch_json(url, {"all": True}).json() == {
        "all": True,
        "unanswered": False,
        "busy": False,
        "unreachable": False,
    }
    # setting one of the three while all=true is rejected
    rejected = client.patch_json(url, {"unreachable": True})
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "validation_error"
    # all still wins when both arrive together
    assert client.patch_json(url, {"all": True, "busy": True}).json()["busy"] is False
    # turning all off in the same request frees the others
    assert client.patch_json(url, {"all": False, "busy": True}).json() == {
        "all": False,
        "unanswered": False,
        "busy": True,
        "unreachable": False,
    }


def test_roaming_toggle(client):
    body = client.get("/api/sim/roaming/").json()
    assert body["enabled"] is False and body["changed_at"] is None
    assert body["texts"]["packs_title"] == "Roaming packs"

    updated = client.patch_json("/api/sim/roaming/", {"enabled": True}).json()
    assert updated["enabled"] is True and updated["changed_at"].endswith("Z")
    assert client.patch_json("/api/sim/roaming/", {}).status_code == 400


def test_sms_settings(client):
    body = client.get("/api/sim/sms/").json()
    assert body["language"] == "az"
    assert body["toggles"] == {"ads": True, "campaigns": True, "partners": True}

    updated = client.patch_json(
        "/api/sim/sms/", {"language": "en", "toggles": {"partners": False}}
    ).json()
    assert updated["language"] == "en"
    assert updated["toggles"] == {"ads": True, "campaigns": True, "partners": False}
    assert client.patch_json("/api/sim/sms/", {"language": "de"}).status_code == 400


def test_puk(client):
    body = client.get("/api/sim/puk/").json()
    assert body["codes"] == [
        {"label": "PUK 1", "value": "5839 0447"},
        {"label": "PUK 2", "value": "8815 4421"},
    ]
    assert body["paragraphs"][0][1] == {"text": "will be blocked", "bold": True}


def test_service_subscription(client):
    rows = client.get("/api/sim/services/").json()["results"]
    missed = next(row for row in rows if row["id"] == "missed-call")
    assert missed["price"] == "0.90" and missed["activated"] is False
    assert missed["badge"] == "AUTO-RENEWAL" and missed["period"] == "30 days"
    detail = client.get("/api/sim/services/missed-call/").json()
    assert detail["action"] == {"kind": "subscribe", "label": "Subscribe for 0.90 ₼"}

    response = client.pay("/api/sim/services/missed-call/subscribe/", {"options": ["xeber-ver"]})
    assert response.status_code == 201
    body = response.json()
    assert body["subscription"]["service"] == "missed-call"
    assert body["subscription"]["status"] == "active"
    assert body["transaction"] == {"title": "Buraxılmış zəng service", "amount": "-0.90"}
    assert body["balance"] == "15.31"

    again = client.pay("/api/sim/services/missed-call/subscribe/", {})
    assert again.status_code == 409 and again.json()["code"] == "already_active"

    rows = client.get("/api/sim/services/").json()["results"]
    missed = next(row for row in rows if row["id"] == "missed-call")
    assert (
        missed["price"] is None and missed["activated"] is True and missed["badge"] == "ACTIVATED"
    )
    assert client.get("/api/sim/services/missed-call/").json()["action"]["kind"] == "deactivate"


def test_service_subscription_errors(client, subscriber):
    unknown = client.pay("/api/sim/services/missed-call/subscribe/", {"options": ["nope"]})
    assert unknown.status_code == 400
    assert client.pay("/api/sim/services/nope/subscribe/", {}).status_code == 404

    subscriber.wallet.balance = "0.50"
    subscriber.wallet.save()
    poor = client.pay("/api/sim/services/missed-call/subscribe/", {})
    assert poor.status_code == 402
    assert poor.json() == {
        "code": "insufficient_balance",
        "detail": "Not enough balance for this service",
    }


def test_esim(client):
    body = client.get("/api/sim/esim/").json()
    assert [b["key"] for b in body["benefits"]] == ["safe", "flexible", "eco"]
    assert body["actions"][1] == {
        "key": "recover",
        "label": "Recover eSIM",
        "deep_link": "/esim/recover",
    }
    response = client.post_json(
        "/api/sim/esim/recover/", {"code": "ABCD-1234", "msisdn": "994516643342"}
    )
    assert response.json()["detail"] == "eSIM recovery is not part of this prototype yet"
