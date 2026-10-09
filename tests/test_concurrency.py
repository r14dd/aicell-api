"""Money under real concurrency, on PostgreSQL.

SQLite serialises writers, so these races can only be shown on a database with
row locks. Run with `DATABASE_URL` pointing at PostgreSQL (see README); on
SQLite the module is skipped.

Each test fires its requests from separate threads, released together by a
barrier, each thread on its own database connection.
"""

import threading
import uuid
from decimal import Decimal

import pytest
from django.db import connection, connections

from api.billing.models import IdempotencyKey, Transaction, Wallet
from api.packs.models import PackActivation
from api.sim.models import ServiceSubscription

from .conftest import client_for

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="needs PostgreSQL row locks (set DATABASE_URL)"
    ),
]


def in_parallel(subscriber, requests):
    """Send every `(path, body, key)` at the same moment; returns the responses in order."""
    barrier = threading.Barrier(len(requests))
    responses = [None] * len(requests)
    errors = []

    def send(index, path, body, key):
        try:
            client = client_for(subscriber)
            barrier.wait(timeout=10)
            responses[index] = client.pay(path, body, key=key)
        except Exception as error:  # surfaced below; a thread must not die silently
            errors.append(error)
        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=send, args=(index, *request))
        for index, request in enumerate(requests)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors, errors
    return responses


def balance_of(subscriber) -> Decimal:
    return Wallet.objects.get(subscriber=subscriber).balance


def key() -> str:
    return str(uuid.uuid4())


def test_two_purchases_that_only_one_balance_covers(subscriber):
    """16.21 on the wallet, two 15.00 packs at once: one is sold, one is refused."""
    purchase = ("/api/packs/internet/purchase/", {"pack_id": "hv-20gb"})
    responses = in_parallel(subscriber, [(*purchase, key()), (*purchase, key())])

    assert sorted(response.status_code for response in responses) == [201, 402]
    assert balance_of(subscriber) == Decimal("1.21")
    assert PackActivation.objects.filter(subscriber=subscriber).count() == 1
    assert Transaction.objects.filter(subscriber=subscriber, kind="purchase").count() == 1


def test_many_purchases_never_take_the_balance_below_zero(subscriber):
    """3.00 on the wallet buys exactly three 0.99 packs, however many are tried at once."""
    Wallet.objects.filter(subscriber=subscriber).update(balance=Decimal("3.00"))
    purchase = ("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"})
    responses = in_parallel(subscriber, [(*purchase, key()) for _ in range(10)])

    statuses = [response.status_code for response in responses]
    assert statuses.count(201) == 3
    assert statuses.count(402) == 7
    assert balance_of(subscriber) == Decimal("0.03")
    assert PackActivation.objects.filter(subscriber=subscriber).count() == 3


def test_parallel_top_ups_are_all_counted(subscriber):
    """No lost update: ten 1.00 top-ups at once add exactly 10.00."""
    top_up = ("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "1.00"})
    responses = in_parallel(subscriber, [(*top_up, key()) for _ in range(10)])

    assert [response.status_code for response in responses] == [201] * 10
    assert balance_of(subscriber) == Decimal("26.21")
    # every response reports a distinct running balance
    assert len({response.json()["balance"] for response in responses}) == 10


def test_the_same_idempotency_key_twice_at_once_charges_once(subscriber):
    shared = key()
    purchase = ("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"}, shared)
    first, second = in_parallel(subscriber, [purchase, purchase])

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert balance_of(subscriber) == Decimal("15.22")
    assert PackActivation.objects.filter(subscriber=subscriber).count() == 1
    assert IdempotencyKey.objects.filter(subscriber=subscriber, key=shared).count() == 1


def test_the_same_key_many_times_at_once_charges_once(subscriber):
    shared = key()
    top_up = ("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "5.00"}, shared)
    responses = in_parallel(subscriber, [top_up] * 8)

    assert {response.status_code for response in responses} == {201}
    # Compared as JSON: PostgreSQL stores the reply as jsonb, which reorders keys.
    assert all(response.json() == responses[0].json() for response in responses)
    assert balance_of(subscriber) == Decimal("21.21")
    assert Transaction.objects.filter(subscriber=subscriber).count() == 3  # 2 seeded + 1


def test_a_service_cannot_be_subscribed_twice_at_once(subscriber):
    """Different keys, same service: one subscription, one `409 already_active`."""
    subscribe = ("/api/sim/services/missed-call/subscribe/", {})
    responses = in_parallel(subscriber, [(*subscribe, key()), (*subscribe, key())])

    assert sorted(response.status_code for response in responses) == [201, 409]
    assert ServiceSubscription.objects.filter(subscriber=subscriber).count() == 1
    assert balance_of(subscriber) == Decimal("15.31")


def test_an_auto_renewing_pack_cannot_be_activated_twice_at_once(subscriber):
    activate = ("/api/packs/social/tehsil/activate/", {"plan_id": "10gb"})
    responses = in_parallel(subscriber, [(*activate, key()), (*activate, key())])

    assert sorted(response.status_code for response in responses) == [201, 409]
    assert PackActivation.objects.filter(subscriber=subscriber, kind="social").count() == 1
    assert balance_of(subscriber) == Decimal("15.51")


def test_different_payments_at_once_add_up(subscriber):
    """A top-up, a purchase and a Steam payment racing each other settle to one balance."""
    responses = in_parallel(
        subscriber,
        [
            ("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "10.00"}, key()),
            ("/api/packs/internet/purchase/", {"pack_id": "daily-1gb"}, key()),
            ("/api/billing/steam/top-up/", {"account": "gamer_01", "amount": "5.00"}, key()),
            ("/api/sim/services/missed-call/subscribe/", {}, key()),
        ],
    )
    assert [response.status_code for response in responses] == [201] * 4
    # 16.21 + 10.00 - 1.00 - 5.00 - 0.90
    assert balance_of(subscriber) == Decimal("19.31")
    total = sum(tx.amount for tx in Transaction.objects.filter(subscriber=subscriber))
    assert Decimal("0.21") + total == balance_of(subscriber)  # 0.21 was carried over
