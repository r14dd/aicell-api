"""A crowd of synthetic subscribers, so the statistics page has something to show.

`seed --crowd N` adds N subscribers in their own msisdn range with 90 days of
usage, top-ups and pack purchases. Each one is built from a random generator
seeded with the subscriber's index, so the same N always gives the same crowd
(relative to the day the seed runs). The named personas are not touched.

A subscriber is built to land in an intended segment: the last 30 days get
exact totals on the right side of the thresholds in `usage.services`. Days
follow a weekly rhythm with noise, and earlier months are a little quieter.
"""

import random
from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils import timezone

from api.common.exceptions import ApiError
from api.referral.models import ReferralProfile
from api.sim.models import SimProfile
from api.usage import offers
from api.usage import services as usage
from api.usage.models import PersonalOffer
from api.users.models import Subscriber

from .stories import MB_PER_GB, Calendar, ledger, split, tariff_from_plan

PREFIX = "9945590"  # 994559000001…: far from the personas (99450100000x) and the demo number
MONTH = 30
MONTHS = 3
DAYS = MONTH * MONTHS

# Out of every 25 subscribers: 10 balanced, 5 heavy data, 5 low usage, 3 voice only, 2 roamers.
MIX = ("balanced",) * 10 + ("heavy_data",) * 5 + ("low_usage",) * 5 + ("voice_only",) * 3
MIX += ("roamer",) * 2
POSTPAID_EVERY = 7  # one subscriber in seven is postpaid

# Share of home data per app, in percent. Each adds up to 100.
APP_MIXES = (
    {"youtube": 48, "kinon": 10, "instagram_facebook": 14, "tiktok": 8, "whatsapp": 6, "other": 14},
    {
        "instagram_facebook": 38,
        "tiktok": 24,
        "youtube": 14,
        "whatsapp": 8,
        "telegram": 4,
        "other": 12,
    },
    {"games": 30, "steam": 12, "youtube": 20, "instagram_facebook": 12, "telegram": 8, "other": 18},
    {
        "whatsapp": 30,
        "telegram": 18,
        "teams": 16,
        "youtube": 12,
        "instagram_facebook": 8,
        "other": 16,
    },
    {
        "youtube": 26,
        "instagram_facebook": 22,
        "tiktok": 10,
        "whatsapp": 12,
        "games": 8,
        "other": 22,
    },
)

# Monday..Sunday: more data at the weekend, more calls on working days.
DATA_RHYTHM = (0.92, 0.9, 0.95, 1.0, 1.08, 1.28, 1.22)
CALL_RHYTHM = (1.12, 1.1, 1.08, 1.05, 1.1, 0.8, 0.7)
EARLIER_MONTHS = (0.86, 0.94)  # 61-90 and 31-60 days ago, against the last 30 days


@dataclass(frozen=True)
class Shape:
    """One subscriber's month: totals for the last 30 days and what goes with them."""

    data_mb: int
    minutes: int
    sms: int
    plan: str
    packs: tuple[tuple[str, int], ...] = ()  # (internet pack slug, bought every N days)
    trips: tuple[int, ...] = ()  # days ago on which a 4-day trip abroad began


def _shape(segment: str, rng: random.Random) -> Shape:
    minutes, sms = rng.randint(40, 220), rng.randint(0, 30)
    if segment == "heavy_data":
        gigabytes = rng.uniform(21, 46)
        plan = "digimax-25" if gigabytes > 30 else "digimax-10"
        packs = (("weekly-5gb", rng.randint(7, 10)), ("unlimited-1d", rng.randint(11, 19)))
        return Shape(int(gigabytes * MB_PER_GB), minutes, sms, plan, packs)
    if segment == "voice_only":
        return Shape(rng.randint(0, 90), rng.randint(60, 320), sms, "digimax-5")
    if segment == "low_usage":
        return Shape(rng.randint(150, 950), rng.randint(4, 28), sms // 4, "digimax-5")
    if segment == "roamer":
        first = rng.randint(4, 24)
        trips = (first, first + MONTH, first + 2 * MONTH)
        return Shape(int(rng.uniform(3, 9) * MB_PER_GB), minutes, sms, "digimax-10", trips=trips)
    gigabytes = rng.uniform(2.5, 9)
    packs = (("weekly-2gb", rng.randint(34, 50)),) if rng.random() < 0.4 else ()
    plan = "digimax-5" if gigabytes < 3.6 else "digimax-10"
    return Shape(int(gigabytes * MB_PER_GB), minutes, sms, plan, packs)


def _scatter(total: int, weights: list[int]) -> list[int]:
    """Whole numbers in proportion to `weights` adding up to `total`, leftovers spread out.

    `stories.spread` puts the whole rounding leftover on the last day, which is
    invisible for one subscriber and a spike on the last day for a crowd.
    """
    if not total or not sum(weights):
        return [0] * len(weights)
    exact = [total * weight / sum(weights) for weight in weights]
    parts = [int(value) for value in exact]
    by_leftover = sorted(range(len(weights)), key=lambda index: parts[index] - exact[index])
    for index in by_leftover[: total - sum(parts)]:
        parts[index] += 1
    return parts


def _by_day(total: int, rhythm, calendar: Calendar, rng: random.Random, skip=()) -> list[int]:
    """`total` for the last 30 days, and a little less for each month before, per day.

    The list runs from 89 days ago (index 0) to today. Each month adds up to
    its own total exactly; within it the days follow `rhythm` with noise.
    """
    result = []
    for month, factor in enumerate((*EARLIER_MONTHS, 1.0)):
        month_total = total if factor == 1 else int(total * factor * rng.uniform(0.94, 1.06))
        weights = []
        for offset in range(MONTH):
            ago = DAYS - 1 - month * MONTH - offset
            weekday = calendar.day(ago).weekday()
            weights.append(
                0 if ago in skip else int(100 * rhythm[weekday] * rng.uniform(0.55, 1.45))
            )
        result += _scatter(month_total, weights)
    return result


def _account(index: int, segment: str) -> Subscriber:
    subscriber = Subscriber.objects.create_user(
        f"{PREFIX}{index:05d}",
        display_name=f"Abunəçi {index}",
        line_type="postpaid" if index % POSTPAID_EVERY == 0 else "prepaid",
        language=("az", "az", "ru", "en")[index % 4],
    )
    SimProfile.objects.create(
        subscriber=subscriber,
        one_way_blocking_date=date(2026, 10, 25),
        deactivation_date=date(2027, 1, 23),
        puk1=f"{30000000 + index}",
        puk2=f"{40000000 + index}",
        roaming_enabled=segment == "roamer",
    )
    ReferralProfile.objects.create(subscriber=subscriber, code=f"crowd{index:05d}")
    return subscriber


def _one(index: int, calendar: Calendar) -> Subscriber:
    rng = random.Random(f"crowd-{index}")  # noqa: S311 - reproducible data, not a secret
    segment = MIX[index % len(MIX)]
    shape = _shape(segment, rng)
    subscriber = _account(index, segment)

    abroad = {start - offset for start in shape.trips for offset in range(4) if start - offset >= 0}
    data = _by_day(shape.data_mb, DATA_RHYTHM, calendar, rng, skip=abroad)
    minutes = _by_day(shape.minutes, CALL_RHYTHM, calendar, rng, skip=abroad)
    sms = _by_day(shape.sms, CALL_RHYTHM, calendar, rng)
    mix = APP_MIXES[rng.randrange(len(APP_MIXES))]
    usage.record_days(
        subscriber,
        [
            usage.Day(
                calendar.day(ago),
                split(data[DAYS - 1 - ago], mix),
                minutes[DAYS - 1 - ago],
                sms[DAYS - 1 - ago],
                *((rng.randint(120, 320), rng.randint(2, 12)) if ago in abroad else (0, 0)),
            )
            for ago in range(DAYS - 1, -1, -1)
        ],
    )
    tariff_from_plan(subscriber, shape.plan, calendar, started_ago=rng.randint(3, 26))

    bought = [
        ("internet", slug, ago)
        for slug, every in shape.packs
        for ago in range(DAYS - 1 - rng.randint(0, every - 1), 0, -every)
    ]
    bought += [("roaming", "r-500mb", start) for start in shape.trips if start < DAYS]
    # Three top-ups, a month apart, that together cover the purchases and leave a little.
    top_up = 5 * (len(bought) * 2 + rng.randint(1, 4))
    paid = [("top_up", f"{top_up}.00", ago) for ago in (DAYS - 1, DAYS - 1 - MONTH, MONTH - 1)]
    ledger(subscriber, calendar, paid + bought)
    return subscriber


def crowd() -> "list[Subscriber]":
    return list(Subscriber.objects.filter(msisdn__startswith=PREFIX).order_by("msisdn"))


@transaction.atomic
def seed_crowd(count: int, reset: bool = False, end: date | None = None) -> tuple[int, bool]:
    """Make the crowd `count` strong. Returns (size, created).

    A crowd of the right size is kept as it is; any other size, or `reset`,
    replaces it, so the result never depends on what was there before.
    """
    existing = Subscriber.objects.filter(msisdn__startswith=PREFIX)
    if existing.count() == count and not reset:
        return count, False
    existing.delete()
    calendar = Calendar(end or timezone.localdate())
    for index in range(1, count + 1):
        _one(index, calendar)
    return count, True


def answer_offers() -> dict[str, int]:
    """Let part of the crowd answer its personal offers, so the sales figures are not all "open".

    Of every ten offers three are accepted (a real purchase at the offer price),
    two are declined and five stay open. Who does what follows from the msisdn.
    """
    answered = {"accepted": 0, "declined": 0}
    open_offers = PersonalOffer.objects.filter(
        subscriber__msisdn__startswith=PREFIX, status__in=PersonalOffer.OPEN
    ).select_related("subscriber")
    for offer in open_offers.order_by("subscriber__msisdn"):
        choice = int(offer.subscriber.msisdn[-5:]) % 10
        try:
            if choice < 3:
                offers.accept(offer.subscriber, offer.id)
                answered["accepted"] += 1
            elif choice < 5:
                offers.decline(offer.subscriber, offer.id)
                answered["declined"] += 1
        except ApiError:
            continue  # not enough balance, or already active: the offer stays open
    return answered
