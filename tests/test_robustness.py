"""No input makes an endpoint answer 500.

Every endpoint of the docs is hit with malformed bodies and query strings;
anything in the 5xx range other than the documented 501 is a bug.
"""

import uuid

import pytest

from .test_docs_conformance import ROWS

BODIES = [
    b"",
    b"{",  # not JSON
    b"null",
    b"[]",
    b'"text"',
    b"12",
    b'{"amount": {}, "pack_id": [], "plan_id": null, "stars": "x", "content": 5}',
    b'{"amount": "1e999", "card_bin": 416300, "options": "xeber-ver", "toggles": []}',
    b'{"amount": "-5", "account": "", "save": "maybe", "language": 7, "all": "x"}',
    '{"amount": "١٢", "content": "\\u0000", "account": "💥"}'.encode(),
]
QUERY = "limit=abc&cursor=%%%&from=2026-13-45&to=x&plan=%00&placement=&q=%F0%9F%92%A5"


def allowed(status):
    return status < 500 or status == 501


@pytest.mark.parametrize("method,path,status", ROWS)
def test_malformed_bodies_never_answer_500(client, method, path, status):
    for body in BODIES:
        response = client.generic(
            method,
            path,
            body,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        assert allowed(response.status_code), f"{method} {path} {body!r} -> {response.content!r}"


@pytest.mark.parametrize("method,path,status", [row for row in ROWS if row[0] == "GET"])
def test_malformed_query_strings_never_answer_500(client, method, path, status):
    joiner = "&" if "?" in path else "?"
    response = client.get(f"{path}{joiner}{QUERY}")
    assert allowed(response.status_code), f"{path} -> {response.content!r}"


@pytest.mark.parametrize("method,path,status", ROWS)
def test_wrong_content_type_never_answers_500(client, method, path, status):
    response = client.generic(method, path, b"a=1", content_type="text/plain")
    assert allowed(response.status_code), f"{method} {path} -> {response.content!r}"


def test_a_subscriber_without_related_rows_gets_404_not_500(catalogue, db):
    """A bare account (no tariff, SIM or referral profile) is a valid state."""
    from api.users.models import Subscriber

    from .conftest import client_for

    bare = client_for(Subscriber.objects.create_user("994550000000"))
    for path in ("/api/tariffs/my/", "/api/sim/", "/api/sim/puk/", "/api/referral/me/"):
        assert bare.get(path).status_code == 404, path
    for path in ("/api/billing/balance/", "/api/content/home/", "/api/assistant/inbox/"):
        assert bare.get(path).status_code == 200, path
