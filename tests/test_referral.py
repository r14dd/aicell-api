from decimal import Decimal

from api.referral.models import ReferralProfile, ReferralStep


def test_invite_page(client, subscriber):
    ReferralProfile.objects.create(subscriber=subscriber, code="AB12CD", earned=Decimal("3"))
    ReferralStep.objects.create(title="Share", body="Send your code")
    body = client.get("/api/referral/me/").json()
    assert body["code"] == "AB12CD"
    assert body["share_url"].endswith("ref=AB12CD")
    assert "AB12CD" in body["share_message"]
    assert body["earned"] == "3.00"
    assert body["steps"] == [{"title": "Share", "body": "Send your code"}]


def test_no_profile_is_404(client):
    assert client.get("/api/referral/me/").status_code == 404


def test_terms_and_events_are_todo(client):
    assert client.get("/api/referral/terms/").status_code == 501
    assert client.post_json("/api/referral/events/").status_code == 501
