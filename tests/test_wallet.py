import uuid
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from api.billing import services
from api.billing.idempotency import idempotent
from api.billing.models import IdempotencyKey, SteamAccount
from api.common.exceptions import InsufficientBalance, InvalidInput


def test_top_up_adds_to_the_balance_and_records_it(subscriber):
    record, balance = services.top_up(subscriber, "card", Decimal("10.00"))
    assert balance == Decimal("10.00")
    assert record.transaction.kind == "top_up"
    assert services.balance_of(subscriber) == Decimal("10.00")
    assert services.top_ups_this_month(subscriber) == Decimal("10.00")


def test_charge_refuses_to_overdraw(subscriber):
    services.top_up(subscriber, "card", Decimal("3.00"))
    with pytest.raises(InsufficientBalance):
        services.charge(subscriber, "5.00", title="Pack", insufficient="Not enough")
    assert services.balance_of(subscriber) == Decimal("3.00")
    _tx, balance = services.charge(subscriber, "2.50", title="Pack", insufficient="Not enough")
    assert balance == Decimal("0.50")


def test_steam_top_up_pays_from_the_balance_and_remembers_the_account(subscriber):
    services.top_up(subscriber, "card", Decimal("20.00"))
    record, balance = services.steam_top_up(subscriber, "gamer_1", Decimal("8.00"), save=True)
    assert balance == Decimal("12.00")
    account = SteamAccount.objects.get(subscriber=subscriber, name="gamer_1")
    assert account.last_amount == Decimal("8.00")
    assert record.transaction.kind == "payment"


def test_purge_removes_only_old_idempotency_keys(subscriber):
    old = IdempotencyKey.objects.create(
        subscriber=subscriber, key=uuid.uuid4(), path="/a", status=200, body={}
    )
    IdempotencyKey.objects.filter(pk=old.pk).update(created_at=timezone.now().replace(year=2020))
    IdempotencyKey.objects.create(
        subscriber=subscriber, key=uuid.uuid4(), path="/b", status=200, body={}
    )
    assert services.purge_idempotency_keys(7) == 1
    assert IdempotencyKey.objects.count() == 1


def _request(subscriber, key=None, path="/pay/"):
    extra = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
    request = APIRequestFactory().post(path, {}, format="json", **extra)
    request.user = subscriber
    return request


def test_idempotent_replays_the_first_answer_and_runs_once(subscriber):
    calls = []

    @idempotent
    def handler(request):
        calls.append(1)
        return {"n": len(calls)}, 201

    key = str(uuid.uuid4())
    first = handler(_request(subscriber, key))
    again = handler(_request(subscriber, key))
    assert (first.status_code, first.data) == (201, {"n": 1})
    assert (again.status_code, again.data) == (201, {"n": 1})
    assert len(calls) == 1


def test_idempotent_needs_a_uuid_key_and_refuses_another_path(subscriber):
    @idempotent
    def handler(request):
        return {}, 200

    with pytest.raises(InvalidInput):
        handler(_request(subscriber))
    with pytest.raises(InvalidInput):
        handler(_request(subscriber, "not-a-uuid"))
    key = str(uuid.uuid4())
    handler(_request(subscriber, key, "/a/"))
    with pytest.raises(InvalidInput):
        handler(_request(subscriber, key, "/b/"))
