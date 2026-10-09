"""Subscriber state: the demo subscriber the mobile prototype is built around."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.color import no_style
from django.db import connection, transaction

from api.assistant.models import Conversation, Message
from api.billing.models import SavedCard, SteamAccount, TopUp, Transaction, Wallet
from api.content.models import Notification
from api.referral.models import ReferralProfile
from api.sim.models import SimProfile
from api.tariffs.models import SubscriberTariff
from api.users.models import Subscriber

from .translations import localized

BAKU = ZoneInfo("Asia/Baku")
DEMO_CONVERSATION_ID = 3513323


@dataclass(frozen=True)
class Profile:
    """What differs between seeded subscribers."""

    display_name: str = "Qüdrət Abidzadə"
    balance: str = "16.21"
    card_last4: str = "4471"
    steam_account: str = "gamer_01"
    referral_code: str = "wa16Kg"
    puk1: str = "58390447"
    puk2: str = "88154421"
    conversation_id: int | None = DEMO_CONVERSATION_ID


def utc(*args):
    return datetime(*args, tzinfo=UTC)


def baku(*args):
    return datetime(*args, tzinfo=BAKU)


def _billing(subscriber, profile):
    # The balance is whatever was carried over plus the two card top-ups below.
    Wallet.objects.create(subscriber=subscriber, balance=Decimal(profile.balance))
    for amount, at in (("1.00", utc(2026, 10, 2, 12, 34)), ("15.00", utc(2026, 10, 2, 12, 39))):
        tx = Transaction.objects.create(
            subscriber=subscriber,
            kind="top_up",
            title="Number balance",
            amount=Decimal(amount),
            created_at=at,
        )
        TopUp.objects.create(
            subscriber=subscriber,
            transaction=tx,
            method="card",
            amount=Decimal(amount),
            created_at=at,
        )
    SavedCard.objects.create(
        subscriber=subscriber,
        brand="mastercard",
        last4=profile.card_last4,
        expiry="09/28",
        is_default=True,
    )
    SteamAccount.objects.create(
        subscriber=subscriber,
        name=profile.steam_account,
        last_amount=Decimal("10.00"),
        last_topped_at=utc(2026, 10, 8, 9, 0),
    )


def _notifications(subscriber):
    rows = [
        {
            "slug": "welcome",
            "title": "Welcome to the new Azercell app",
            "body": "Manage your number, tariff and payments in one place.",
            "sent_at": utc(2025, 9, 15, 9, 0),
            "read_at": utc(2025, 9, 15, 10, 0),
        },
        {
            "slug": "wingz",
            "title": "Activate Wingz scooter with your Azercell balance!",
            "body": "Get 15 minutes of free time on your first Wingz ride when you pay "
            "with your Azercell balance.",
            "sent_at": utc(2025, 10, 27, 9, 0),
        },
        {
            "slug": "lottery",
            "title": "30 il səninlə",
            "body": "Chance collection starts on 19 October 2026.",
            "cta": {"label": "Learn more about the lottery", "deep_link": "/lottery-rules"},
            "sent_at": utc(2026, 10, 1, 9, 0),
        },
    ]
    for row in rows:
        Notification.objects.create(subscriber=subscriber, **localized(Notification, row))


def _advance_sequence(model):
    """After inserting an explicit id, move the id sequence past it (PostgreSQL)."""
    statements = connection.ops.sequence_reset_sql(no_style(), [model])
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def _conversation(subscriber, conversation_id):
    conversation = Conversation.objects.create(
        id=conversation_id,
        subscriber=subscriber,
        status="closed",
        unread=True,
        created_at=utc(2026, 10, 6, 14, 0),
        last_message_at=utc(2026, 10, 6, 14, 1),
    )
    Message.objects.create(
        conversation=conversation,
        role="user",
        content="How much internet do I have left?",
        created_at=utc(2026, 10, 6, 14, 0),
    )
    Message.objects.create(
        conversation=conversation,
        role="assistant",
        route="usage",
        content="You have 7.20 GB left until 25 October.",
        action={
            "action": "navigate",
            "to": "/remaining-balance",
            "label": "Open remaining balance",
        },
        created_at=utc(2026, 10, 6, 14, 1),
    )
    _advance_sequence(Conversation)


@transaction.atomic
def seed_subscriber(msisdn: str, profile: Profile | None = None) -> Subscriber:
    """Create a subscriber with a wallet, tariff, SIM, notifications and a conversation."""
    profile = profile or Profile()
    subscriber = Subscriber.objects.create_user(
        msisdn, display_name=profile.display_name, line_type="prepaid", language="en"
    )
    _billing(subscriber, profile)
    SubscriberTariff.objects.create(
        subscriber=subscriber,
        activated_at=baku(2026, 9, 24),
        last_payment_at=baku(2026, 9, 24),
        next_payment_at=baku(2026, 10, 25, 8),
    )
    SimProfile.objects.create(
        subscriber=subscriber,
        one_way_blocking_date=date(2026, 10, 25),
        deactivation_date=date(2027, 1, 23),
        puk1=profile.puk1,
        puk2=profile.puk2,
    )
    _notifications(subscriber)
    ReferralProfile.objects.create(subscriber=subscriber, code=profile.referral_code)
    if profile.conversation_id:
        _conversation(subscriber, profile.conversation_id)
    return subscriber


@transaction.atomic
def seed_demo(reset: bool = False) -> tuple[Subscriber, bool]:
    """Create the demo subscriber. Returns (subscriber, created)."""
    existing = Subscriber.objects.filter(msisdn=settings.DEMO_MSISDN).first()
    if existing and not reset:
        return existing, False
    if existing:
        existing.delete()
    return seed_subscriber(settings.DEMO_MSISDN), True
