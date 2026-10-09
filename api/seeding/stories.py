"""Thirty-day stories for the seeded subscribers.

Each story is usage per day, the purchases that go with it and a tariff, built
so that the numbers add up: the wallet is the sum of its transactions, the
tariff's remaining amounts follow from the usage, and add-on packs are bought
after the included data ran out.

This is synthetic data. Days are counted back from the day the seed runs, so a
freshly seeded database always holds "the last 30 days".
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from api.billing.models import TopUp, Transaction, Wallet
from api.packs.models import InternetPack, PackActivation, RoamingPack
from api.referral.models import ReferralProfile
from api.sim.models import ServiceSubscription, SimProfile, SimService
from api.tariffs.models import SubscriberTariff, TariffPlan
from api.usage import services as usage
from api.usage.models import DailyUsage, OfferRule, PersonalOffer
from api.users.models import Subscriber

BAKU = ZoneInfo("Asia/Baku")
DAYS = 30
MB_PER_GB = 1024

TEST_NUMBERS = ("994501000001", "994501000002", "994501000003", "994501000004")
DEMO_OFFER_ID = 9001
DEMO_INSIGHT_ID = 9101
DEMO_OFFER = ("social_pack", "instagram-facebook:5gb")

# Share of home data per app, in percent. Each adds up to 100.
YOUTUBE_FAN = {
    "youtube": 62, "instagram_facebook": 14, "tiktok": 6, "whatsapp": 6, "games": 4, "other": 8
}  # fmt: skip
TRAVELLER = {
    "youtube": 20, "instagram_facebook": 25, "whatsapp": 20, "telegram": 10, "other": 25
}  # fmt: skip
GAMER = {"games": 38, "youtube": 22, "instagram_facebook": 15, "whatsapp": 10, "other": 15}
INSTAGRAMMER = {"instagram_facebook": 55, "youtube": 15, "tiktok": 5, "whatsapp": 6, "other": 19}


def spread(total: int, weights: list[int]) -> list[int]:
    """Whole numbers in proportion to `weights` that add up to exactly `total`."""
    if not total or not sum(weights):
        return [0] * len(weights)
    parts = [total * weight // sum(weights) for weight in weights]
    last = max(index for index, weight in enumerate(weights) if weight)
    parts[last] += total - sum(parts)
    return parts


def split(total: int, shares: dict[str, int]) -> dict[str, int]:
    """`total` divided between apps by percent, adding up to exactly `total`."""
    return dict(zip(shares, spread(total, list(shares.values())), strict=True))


@dataclass(frozen=True)
class Calendar:
    """Days counted back from the seed day: `ago=0` is today."""

    end: date

    def day(self, ago: int) -> date:
        return self.end - timedelta(days=ago)

    def at(self, ago: int, hour: int = 12) -> datetime:
        return datetime.combine(self.day(ago), time(hour), tzinfo=BAKU)


def record(
    subscriber,
    calendar: Calendar,
    *,
    data: list[int],
    shares: dict[str, int],
    minutes: list[int],
    sms: list[int],
    roaming: dict[int, tuple[int, int]] | None = None,
) -> None:
    """Store 30 days of usage. Lists run from 29 days ago (index 0) to today."""
    roaming = roaming or {}
    days = []
    for index in range(DAYS):
        ago = DAYS - 1 - index
        roaming_mb, roaming_minutes = roaming.get(ago, (0, 0))
        days.append(
            usage.Day(
                calendar.day(ago),
                split(data[index], shares),
                minutes[index],
                sms[index],
                roaming_mb,
                roaming_minutes,
            )
        )
    usage.record_days(subscriber, days)


# --- account pieces -----------------------------------------------------------


def account(msisdn: str, index: int) -> Subscriber:
    subscriber = Subscriber.objects.create_user(
        msisdn, display_name=f"Test Abunəçi {index}", line_type="prepaid", language="az"
    )
    SimProfile.objects.create(
        subscriber=subscriber,
        one_way_blocking_date=date(2026, 10, 25),
        deactivation_date=date(2027, 1, 23),
        puk1=f"{10000000 + index}",
        puk2=f"{20000000 + index}",
    )
    ReferralProfile.objects.create(subscriber=subscriber, code=f"test{index:02d}")
    return subscriber


def tariff_from_plan(subscriber, plan_slug: str, calendar: Calendar, started_ago: int):
    """Put the subscriber on a catalogue plan whose period began `started_ago` days ago."""
    plan = TariffPlan.objects.select_related("family").get(slug=plan_slug)
    if plan.data_mb is None or plan.minutes is None:
        raise ValueError(f"Plan {plan_slug} has no included amounts; run `seed --refresh`")
    start = calendar.at(started_ago, hour=0)
    in_period = DailyUsage.objects.filter(subscriber=subscriber, day__gte=start.date())
    used_mb = sum(row.data_mb for row in in_period)
    used_minutes = sum(row.call_minutes for row in in_period)
    left_mb = max(0, plan.data_mb - used_mb)
    return SubscriberTariff.objects.create(
        subscriber=subscriber,
        family=plan.family.slug,
        plan_slug=plan.slug,
        title=plan.title_en,
        price=plan.price,
        validity_days=28,
        activated_at=start,
        last_payment_at=start,
        next_payment_at=start + timedelta(days=28),
        data_total_gb=plan.data_mb // MB_PER_GB,
        data_remaining_gb=(Decimal(left_mb) / MB_PER_GB).quantize(Decimal("0.01")),
        minutes_total=plan.minutes,
        minutes_remaining=max(0, plan.minutes - used_minutes),
    )


def ledger(subscriber, calendar: Calendar, entries: list[tuple[str, str, int]]) -> None:
    """Write dated wallet movements; the balance is their sum.

    An entry is `(kind, what, days_ago)`: a top-up amount, or the slug of an
    internet pack, roaming pack or SIM service that was bought.
    """
    balance = Decimal("0.00")
    for kind, what, ago in sorted(entries, key=lambda entry: -entry[2]):
        when = calendar.at(ago)
        if kind == "top_up":
            amount = Decimal(what)
            tx = _movement(subscriber, "top_up", "Number balance", amount, when)
            TopUp.objects.create(
                subscriber=subscriber, transaction=tx, method="card", amount=amount, created_at=when
            )
        elif kind == "internet":
            pack = InternetPack.objects.get(slug=what)
            amount = -pack.price
            tx = _movement(subscriber, "purchase", f"{pack.label_en} pack", amount, when)
            _activation(
                subscriber, tx, "internet", pack.slug, pack.label_en, when, hours=pack.hours
            )
        elif kind == "roaming":
            pack = RoamingPack.objects.get(slug=what)
            amount = -pack.price
            label = f"Roaming {pack.name_en}"
            tx = _movement(subscriber, "purchase", f"{label} pack", amount, when)
            _activation(subscriber, tx, "roaming", pack.slug, label, when, hours=pack.days * 24)
        else:
            service = SimService.objects.get(slug=what)
            amount = -service.price
            tx = _movement(subscriber, "purchase", f"{service.name_en} service", amount, when)
            ServiceSubscription.objects.create(
                subscriber=subscriber,
                transaction=tx,
                service=service.slug,
                created_at=when,
                next_payment_at=when + timedelta(days=service.days),
            )
        balance += amount
    Wallet.objects.create(subscriber=subscriber, balance=balance)


def _movement(subscriber, kind, title, amount, when) -> Transaction:
    return Transaction.objects.create(
        subscriber=subscriber, kind=kind, title=title, amount=amount, created_at=when
    )


def _activation(subscriber, tx, kind, slug, label, when, *, hours) -> None:
    expires = when + timedelta(hours=hours)
    PackActivation.objects.create(
        subscriber=subscriber,
        transaction=tx,
        kind=kind,
        pack_id=slug,
        label=label,
        status="active" if expires > timezone.now() else "expired",
        activated_at=when,
        expires_at=expires,
    )


# --- the five stories ---------------------------------------------------------


def heavy_youtube(msisdn: str, calendar: Calendar) -> Subscriber:
    """On DigiMax 5GB, used up in three days; five add-on packs bought since."""
    subscriber = account(msisdn, 1)
    before = [400] * 9  # the tail of the previous period
    burst = [2000, 2200, 1500]  # 5.7 GB in the first three days of a 5 GB plan
    after = spread(24000 - sum(before) - sum(burst), [1] * 18)
    record(
        subscriber,
        calendar,
        data=before + burst + after,
        shares=YOUTUBE_FAN,
        minutes=[2] * DAYS,
        sms=[1 if index % 3 == 0 else 0 for index in range(DAYS)],
    )
    tariff_from_plan(subscriber, "digimax-5", calendar, started_ago=20)
    ledger(
        subscriber,
        calendar,
        [
            ("top_up", "25.00", 19),
            ("internet", "weekly-5gb", 17),
            ("internet", "unlimited-1d", 12),
            ("internet", "weekly-5gb", 10),
            ("internet", "unlimited-1d", 6),
            ("internet", "weekly-5gb", 4),
        ],
    )
    return subscriber


def voice_only(msisdn: str, calendar: Calendar) -> Subscriber:
    """Calls and a few SMS; has never used mobile data or bought a pack."""
    subscriber = account(msisdn, 2)
    record(
        subscriber,
        calendar,
        data=[0] * DAYS,
        shares={"other": 100},
        minutes=spread(92, ([4, 2, 3, 5, 1, 3, 4] * 5)[:DAYS]),
        sms=[1 if index % 5 == 0 else 0 for index in range(DAYS)],
    )
    tariff_from_plan(subscriber, "digimax-5", calendar, started_ago=20)
    ledger(subscriber, calendar, [("top_up", "5.00", 9)])
    return subscriber


ROAMING_DAYS = (26, 25, 24, 15, 14, 13, 5, 4, 3)  # three trips, in days ago


def roamer(msisdn: str, calendar: Calendar) -> Subscriber:
    """Three trips abroad in a month, each paid with small 500 MB roaming packs."""
    subscriber = account(msisdn, 3)
    at_home = [0 if DAYS - 1 - index in ROAMING_DAYS else 1 for index in range(DAYS)]
    record(
        subscriber,
        calendar,
        data=spread(6000, at_home),
        shares=TRAVELLER,
        minutes=spread(140, at_home),
        sms=[0] * DAYS,
        roaming=dict.fromkeys(ROAMING_DAYS, (200, 5)),
    )
    tariff_from_plan(subscriber, "digimax-10", calendar, started_ago=20)
    ledger(
        subscriber,
        calendar,
        [
            ("top_up", "50.00", 27),
            ("roaming", "r-500mb", 26),
            ("roaming", "r-500mb", 15),
            ("roaming", "r-500mb", 14),
            ("roaming", "r-500mb", 5),
        ],
    )
    return subscriber


def balanced(msisdn: str, calendar: Calendar) -> Subscriber:
    """Uses about three quarters of DigiMax 10GB and buys nothing extra: the plan fits."""
    subscriber = account(msisdn, 4)
    record(
        subscriber,
        calendar,
        data=spread(7400, [1] * DAYS),
        shares=GAMER,
        minutes=[5] * DAYS,
        sms=spread(40, [1] * DAYS),
    )
    tariff_from_plan(subscriber, "digimax-10", calendar, started_ago=20)
    ledger(subscriber, calendar, [("top_up", "10.00", 15), ("service", "missed-call", 12)])
    return subscriber


STORIES = dict(zip(TEST_NUMBERS, (heavy_youtube, voice_only, roamer, balanced), strict=True))


def demo_usage(subscriber, calendar: Calendar) -> None:
    """The demo subscriber on IsteSen: moderate use, more than half of it Instagram.

    Its tariff and wallet are fixed by the original seed, so only usage is
    added; the usage is close to, not derived from, the tariff's remaining 7.2 GB.
    """
    record(
        subscriber,
        calendar,
        data=spread(13000, [1] * DAYS),
        shares=INSTAGRAMMER,
        minutes=spread(20, [1 if index % 3 == 0 else 0 for index in range(DAYS)]),
        sms=spread(6, [1 if index % 5 == 0 else 0 for index in range(DAYS)]),
    )


def demo_offer(subscriber, offer_id: int) -> PersonalOffer:
    """An open offer placed by hand, so the offer endpoints have something to show.

    It points at the seeded rule for this item, which is switched off: the rule
    carries the translated reason but is not applied to anyone automatically.
    """
    from api.usage import offers

    kind, target_id = DEMO_OFFER
    rule = OfferRule.objects.filter(target_kind=kind, target_id=target_id).first()
    now = timezone.now()
    return PersonalOffer.objects.create(
        id=offer_id,
        subscriber=subscriber,
        rule=rule,
        target_kind=kind,
        target_id=target_id,
        normal_price=offers.resolve(kind, target_id).price,
        offer_price=rule.offer_price if rule else Decimal("2.00"),
        reason=rule.reason if rule else "",
        created_at=now,
        expires_at=now + timedelta(days=14),
    )


def demo_insight(subscriber, insight_id: int):
    """The most urgent insight the demo usage really gives, stored under a fixed id."""
    from api.insights import services as insights
    from api.insights.models import Insight

    found = insights.detect(subscriber)
    if not found:
        return None
    first = found[0]
    return Insight.objects.create(
        id=insight_id,
        subscriber=subscriber,
        kind=first.kind,
        evidence=first.evidence,
        offers=first.offers,
    )


def _untouched(subscriber) -> bool:
    """An account from before the stories existed: no usage and no wallet movement."""
    return not (
        DailyUsage.objects.filter(subscriber=subscriber).exists()
        or Transaction.objects.filter(subscriber=subscriber).exists()
    )


@transaction.atomic
def seed_test_numbers(reset: bool = False, end: date | None = None) -> list[Subscriber]:
    """Create the four personas. Existing ones are kept unless `reset` or still empty."""
    calendar = Calendar(end or timezone.localdate())
    subscribers = []
    for msisdn, story in STORIES.items():
        existing = Subscriber.objects.filter(msisdn=msisdn).first()
        if existing and (reset or _untouched(existing)):
            existing.delete()
            existing = None
        subscribers.append(existing or story(msisdn, calendar))
    return subscribers
