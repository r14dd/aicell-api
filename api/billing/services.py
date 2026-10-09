"""Wallet rules: every balance change goes through `move`, which records it."""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from api.common.exceptions import InsufficientBalance

from .models import IdempotencyKey, SavedAkart, SteamAccount, SteamTopUp, TopUp, Transaction, Wallet


def balance_of(subscriber) -> Decimal:
    wallet, _created = Wallet.objects.get_or_create(subscriber=subscriber)
    return wallet.balance


def lock_wallet(subscriber) -> Wallet:
    """Lock the subscriber's wallet row until the surrounding transaction ends.

    Every balance change takes this lock first, so the balance check and the
    write cannot interleave with another request. It also serves as the
    per-subscriber lock for "only once" rules such as an already active service.
    """
    Wallet.objects.get_or_create(subscriber=subscriber)
    return Wallet.objects.select_for_update().get(subscriber=subscriber)


@transaction.atomic
def move(subscriber, amount, *, kind, title, insufficient=None) -> tuple[Transaction, Decimal]:
    """Apply a signed amount to the wallet and record it. Returns (transaction, balance).

    The check against the balance and the write happen under the same row lock.
    """
    wallet = lock_wallet(subscriber)
    amount = Decimal(amount)
    if wallet.balance + amount < 0:
        raise InsufficientBalance(insufficient)
    wallet.balance += amount
    wallet.save(update_fields=["balance"])
    tx = Transaction.objects.create(subscriber=subscriber, kind=kind, title=title, amount=amount)
    return tx, wallet.balance


def charge(
    subscriber, price, *, title, insufficient, kind="purchase"
) -> tuple[Transaction, Decimal]:
    return move(subscriber, -Decimal(price), kind=kind, title=title, insufficient=insufficient)


def top_ups_this_month(subscriber) -> Decimal:
    """Sum of completed top-ups since the first of the month, in Asia/Baku."""
    now = timezone.localtime()
    month_start = datetime.combine(now.date().replace(day=1), time.min, tzinfo=now.tzinfo)
    total = TopUp.objects.filter(
        subscriber=subscriber, status="completed", created_at__gte=month_start
    ).aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")


@transaction.atomic
def top_up(subscriber, method, amount) -> tuple[TopUp, Decimal]:
    tx, balance = move(subscriber, amount, kind="top_up", title=_("Number balance"))
    record = TopUp.objects.create(
        subscriber=subscriber, transaction=tx, method=method, amount=amount
    )
    return record, balance


def save_akart(subscriber, msisdn) -> SavedAkart:
    saved, _created = SavedAkart.objects.get_or_create(subscriber=subscriber, msisdn=msisdn)
    return saved


@transaction.atomic
def steam_top_up(subscriber, account, amount, *, save) -> tuple[SteamTopUp, Decimal]:
    """Pay a Steam account from the balance, remembering the account when asked."""
    tx, balance = charge(
        subscriber,
        amount,
        title=_("Steam balance %(account)s") % {"account": account},
        insufficient=_("Not enough balance for this top-up"),
        kind="payment",
    )
    record = SteamTopUp.objects.create(
        subscriber=subscriber, transaction=tx, account=account, amount=amount
    )
    if save:
        SteamAccount.objects.get_or_create(subscriber=subscriber, name=account)
    SteamAccount.objects.filter(subscriber=subscriber, name=account).update(
        last_amount=amount, last_topped_at=record.created_at
    )
    return record, balance


def purge_idempotency_keys(older_than_days: int = 7) -> int:
    """Delete stored replies of old money requests. Returns how many."""
    cutoff = timezone.now() - timedelta(days=older_than_days)
    deleted, _details = IdempotencyKey.objects.filter(created_at__lt=cutoff).delete()
    return deleted
