"""Usage history and the profile built from it.

`record_usage` is the single way usage gets in. A real network feed would call
it; this prototype is not connected to an operator network, so the only caller
today is the seed.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from api.billing.models import Transaction
from api.packs.models import PackActivation
from api.sim.models import ServiceSubscription
from api.tariffs.models import SubscriberTariff

from . import taxonomy
from .models import AppUsage, DailyUsage

DEFAULT_DAYS = 30
MB_PER_GB = 1024

# --- segment thresholds, per window ------------------------------------------
HEAVY_DATA_MB = 20 * MB_PER_GB  # this much data, or...
HEAVY_ADDON_PURCHASES = 3  # ...this many add-on packs, or running out of data
VOICE_ONLY_MAX_DATA_MB = 100
VOICE_ONLY_MIN_MINUTES = 30
ROAMER_MIN_DAYS = 3
LOW_USAGE_MAX_DATA_MB = MB_PER_GB
LOW_USAGE_MAX_MINUTES = 30

ADDON_KINDS = ("internet", "social")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Day:
    """What one subscriber used on one day. Home data is given per app."""

    day: date
    data_by_app: dict[str, int] = field(default_factory=dict)
    call_minutes: int = 0
    sms: int = 0
    roaming_data_mb: int = 0
    roaming_minutes: int = 0
    overage_mb: int = 0
    overage_amount: Decimal = Decimal("0")


@transaction.atomic
def record_days(subscriber, days: list[Day]) -> None:
    """Store usage for many days at once, replacing what was stored for those days.

    The same rules as `record_usage`, in a handful of queries however many
    days are given. An unknown app key raises before anything is written.
    """
    for entry in days:
        for app in entry.data_by_app:
            taxonomy.category_of(app)

    dates = [entry.day for entry in days]
    DailyUsage.objects.filter(subscriber=subscriber, day__in=dates).delete()
    AppUsage.objects.filter(subscriber=subscriber, day__in=dates).delete()
    DailyUsage.objects.bulk_create(
        DailyUsage(
            subscriber=subscriber,
            day=entry.day,
            data_mb=sum(entry.data_by_app.values()),
            call_minutes=entry.call_minutes,
            sms=entry.sms,
            roaming_data_mb=entry.roaming_data_mb,
            roaming_minutes=entry.roaming_minutes,
            overage_mb=entry.overage_mb,
            overage_amount=entry.overage_amount,
        )
        for entry in days
    )
    AppUsage.objects.bulk_create(
        AppUsage(subscriber=subscriber, day=entry.day, app=app, data_mb=data_mb)
        for entry in days
        for app, data_mb in entry.data_by_app.items()
        if data_mb
    )


def record_usage(
    subscriber,
    day: date,
    *,
    data_by_app: dict[str, int] | None = None,
    call_minutes: int = 0,
    sms: int = 0,
    roaming_data_mb: int = 0,
    roaming_minutes: int = 0,
) -> DailyUsage:
    """Store what a subscriber used on a day, replacing what was stored for it.

    Calling it again with the same input changes nothing. Home data is given
    per app; the day's total is their sum. An app key that is not in
    `taxonomy.CATEGORIES` raises `taxonomy.UnknownApp` and nothing is stored.
    """
    entry = Day(day, data_by_app or {}, call_minutes, sms, roaming_data_mb, roaming_minutes)
    record_days(subscriber, [entry])
    return DailyUsage.objects.get(subscriber=subscriber, day=day)


# --- profile ------------------------------------------------------------------


@dataclass(frozen=True)
class Spend:
    """What the subscriber paid in the window."""

    tariff_fee: Decimal
    addon_count: int
    addon_amount: Decimal
    roaming_count: int
    roaming_amount: Decimal
    other: Decimal

    @property
    def plan_related(self) -> Decimal:
        """Tariff, add-on packs and roaming: the part a different setup could change."""
        return self.tariff_fee + self.addon_amount + self.roaming_amount

    @property
    def total(self) -> Decimal:
        return self.plan_related + self.other


@dataclass(frozen=True)
class RanOut:
    """Included data was used up on this day of the tariff period."""

    day: int
    date: date
    period_days: int


@dataclass(frozen=True)
class Profile:
    days: int
    start: date
    end: date
    data_mb: int
    minutes: int
    sms: int
    roaming_data_mb: int
    roaming_minutes: int
    roaming_days: int
    by_app: tuple[tuple[str, int], ...]  # (app, MB), largest first
    ran_out: RanOut | None
    spend: Spend
    services: tuple[str, ...]  # slugs of active paid SIM services
    tariff: SubscriberTariff | None
    segment: str

    @property
    def by_category(self) -> tuple[tuple[str, int], ...]:
        totals: dict[str, int] = {}
        for app, data_mb in self.by_app:
            category = taxonomy.category_of(app)
            totals[category] = totals.get(category, 0) + data_mb
        return tuple(sorted(totals.items(), key=lambda item: -item[1]))

    def app_mb(self, app: str) -> int:
        return dict(self.by_app).get(app, 0)

    def share(self, data_mb: int) -> float:
        return round(data_mb / self.data_mb, 2) if self.data_mb else 0.0


def today() -> date:
    return timezone.localdate()


def _spend(subscriber, tariff, start, end) -> Spend:
    in_window = {"created_at__date__gte": start, "created_at__date__lte": end}
    spent = Transaction.objects.filter(subscriber=subscriber, amount__lt=0, **in_window).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")

    packs = {
        row["kind"]: row
        for row in PackActivation.objects.filter(
            subscriber=subscriber,
            transaction__created_at__date__gte=start,
            transaction__created_at__date__lte=end,
        )
        .values("kind")
        .annotate(count=Count("id"), amount=Sum("transaction__amount"))
    }

    def of(kinds):
        rows = [packs[kind] for kind in kinds if kind in packs]
        amount = -sum((row["amount"] for row in rows), Decimal("0"))
        return sum(row["count"] for row in rows), amount.quantize(CENT)

    addon_count, addon_amount = of(ADDON_KINDS)
    roaming_count, roaming_amount = of(("roaming",))
    return Spend(
        # The tariff fee is not a wallet transaction in this prototype: the
        # tariff record holds the price of the period, so that is what is used.
        tariff_fee=tariff.price if tariff else Decimal("0"),
        addon_count=addon_count,
        addon_amount=addon_amount,
        roaming_count=roaming_count,
        roaming_amount=roaming_amount,
        other=(-spent - addon_amount - roaming_amount).quantize(CENT),
    )


def _ran_out(subscriber, tariff, end) -> RanOut | None:
    """The day of the current tariff period on which included data was used up."""
    if tariff is None:
        return None
    period_start = timezone.localtime(tariff.last_payment_at).date()
    included = tariff.data_total_gb * MB_PER_GB
    used = 0
    rows = DailyUsage.objects.filter(subscriber=subscriber, day__gte=period_start, day__lte=end)
    for row in rows.order_by("day"):
        used += row.data_mb
        if used > included:
            return RanOut((row.day - period_start).days + 1, row.day, tariff.validity_days)
    return None


def segment_of(*, data_mb, minutes, roaming_days, addon_count, ran_out) -> str:
    """One label for how the subscriber uses the number. First match wins."""
    if roaming_days >= ROAMER_MIN_DAYS:
        return "roamer"
    if data_mb <= VOICE_ONLY_MAX_DATA_MB and minutes >= VOICE_ONLY_MIN_MINUTES:
        return "voice_only"
    if data_mb >= HEAVY_DATA_MB or addon_count >= HEAVY_ADDON_PURCHASES or ran_out:
        return "heavy_data"
    if data_mb <= LOW_USAGE_MAX_DATA_MB and minutes <= LOW_USAGE_MAX_MINUTES:
        return "low_usage"
    return "balanced"


def profile(subscriber, days: int = DEFAULT_DAYS, end: date | None = None) -> Profile:
    """What the subscriber did in the last `days` days, ending today."""
    end = end or today()
    start = end - timedelta(days=days - 1)
    in_window = {"subscriber": subscriber, "day__gte": start, "day__lte": end}

    totals = DailyUsage.objects.filter(**in_window).aggregate(
        data_mb=Sum("data_mb"),
        minutes=Sum("call_minutes"),
        sms=Sum("sms"),
        roaming_data_mb=Sum("roaming_data_mb"),
        roaming_minutes=Sum("roaming_minutes"),
    )
    totals = {key: value or 0 for key, value in totals.items()}
    roaming_days = (
        DailyUsage.objects.filter(**in_window).exclude(roaming_data_mb=0, roaming_minutes=0).count()
    )
    by_app = tuple(
        (row["app"], row["data_mb"])
        for row in AppUsage.objects.filter(**in_window)
        .values("app")
        .annotate(data_mb=Sum("data_mb"))
        .order_by("-data_mb", "app")
    )

    tariff = SubscriberTariff.objects.filter(subscriber=subscriber).first()
    spend = _spend(subscriber, tariff, start, end)
    ran_out = _ran_out(subscriber, tariff, end)
    services = tuple(
        ServiceSubscription.objects.filter(subscriber=subscriber, status="active")
        .order_by("id")
        .values_list("service", flat=True)
    )
    return Profile(
        days=days,
        start=start,
        end=end,
        by_app=by_app,
        ran_out=ran_out,
        spend=spend,
        services=services,
        tariff=tariff,
        roaming_days=roaming_days,
        segment=segment_of(
            data_mb=totals["data_mb"],
            minutes=totals["minutes"],
            roaming_days=roaming_days,
            addon_count=spend.addon_count,
            ran_out=ran_out,
        ),
        **totals,
    )
