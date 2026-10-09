"""The figures every detector reads, worked out once per subscriber.

Everything here is arithmetic over rows that already exist: daily usage, per-app
usage, pack activations, the tariff and the wallet. "Per month" figures are the
last 60 days scaled to 30, or as many days as there is history for.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from api.billing import services as billing
from api.billing.models import SavedCard
from api.packs.models import PackActivation
from api.tariffs import services as tariffs
from api.tariffs.models import SubscriberTariff
from api.usage.models import AppUsage, DailyUsage

MB_PER_GB = 1024
BURN_DAYS = 7
SHARE_DAYS = 30
PROFILE_DAYS = 60
RECENT_ROAMING_DAYS = 3
MAX_PERIODS = 3
ADDON_KINDS = ("internet", "social")
VIDEO_APPS = ("youtube", "tiktok")
SOCIAL_APP = "instagram_facebook"
ZERO = Decimal("0")


@dataclass(frozen=True)
class Purchase:
    """An add-on pack that was bought."""

    kind: str
    pack_id: str
    price: Decimal
    at: datetime


@dataclass(frozen=True)
class Period:
    """A finished tariff period and how much of its internet was used."""

    start: date
    end: date
    used_mb: int
    included_mb: int

    @property
    def unused_mb(self) -> int:
        return max(0, self.included_mb - self.used_mb)

    @property
    def unused_share(self) -> float:
        return self.unused_mb / self.included_mb if self.included_mb else 0.0


@dataclass(frozen=True)
class Metrics:
    now: datetime
    today: date
    tariff: SubscriberTariff
    balance: Decimal
    next_price: Decimal  # what the coming renewal costs
    has_card: bool
    burn_mb_day: float  # average home data per day, last 7 days
    data_by_day: dict[date, int]  # home data, last 60 days
    apps_by_day: dict[date, dict[str, int]]
    by_app_mb: dict[str, int]  # last 30 days
    span_days: int  # days of history behind the monthly figures, at most 60
    by_app_mb_month: dict[str, float]
    minutes_month: float
    overage_mb_today: int
    overage_amount_today: Decimal
    overage_amount_month: Decimal
    roaming_mb_recent: int  # last 3 days
    roaming_active: bool  # a roaming pack is running
    purchases: tuple[Purchase, ...]  # add-on packs of the last 60 days, newest first
    periods: tuple[Period, ...]  # finished periods with full history, newest first

    # --- the tariff period ----------------------------------------------------

    @property
    def remaining_mb(self) -> int:
        return int(self.tariff.data_remaining_gb * MB_PER_GB)

    @property
    def included_mb(self) -> int:
        return self.tariff.data_total_gb * MB_PER_GB

    @property
    def used_share(self) -> float:
        return 1 - self.remaining_mb / self.included_mb if self.included_mb else 0.0

    @property
    def days_left(self) -> float:
        return max(0.0, (self.tariff.next_payment_at - self.now).total_seconds() / 86400)

    @property
    def days_to_empty(self) -> float | None:
        """Days the remaining internet lasts at the current rate; None when nothing is used."""
        return self.remaining_mb / self.burn_mb_day if self.burn_mb_day else None

    @property
    def gap_mb(self) -> float:
        """How much internet will be missing before the renewal. Positive = it will not last."""
        return self.burn_mb_day * self.days_left - self.remaining_mb

    @property
    def renewal_shortfall(self) -> Decimal:
        return max(ZERO, self.next_price - self.balance)

    # --- how the data is used -------------------------------------------------

    @property
    def data_mb(self) -> int:
        return sum(self.by_app_mb.values())

    def share(self, *apps: str) -> float:
        used = sum(self.by_app_mb.get(app, 0) for app in apps)
        return used / self.data_mb if self.data_mb else 0.0

    @property
    def video_share(self) -> float:
        return self.share(*VIDEO_APPS)

    @property
    def social_share(self) -> float:
        return self.share(SOCIAL_APP)

    @property
    def data_mb_month(self) -> float:
        return sum(self.by_app_mb_month.values())

    # --- what is paid ---------------------------------------------------------

    @property
    def period_purchases(self) -> tuple[Purchase, ...]:
        """Add-on packs bought since the current period began."""
        return tuple(p for p in self.purchases if p.at >= self.tariff.last_payment_at)

    @property
    def packs_month(self) -> Decimal:
        total = sum((purchase.price for purchase in self.purchases), ZERO)
        return _monthly(total, self.span_days)

    @property
    def monthly_spend(self) -> Decimal:
        """Tariff, add-on packs and out-of-package traffic, per month."""
        return self.tariff.price + self.packs_month + self.overage_amount_month


def local_day(moment: datetime) -> date:
    """The calendar day of a moment in Asia/Baku."""
    return timezone.localtime(moment).date()


def _monthly(amount, span_days: int) -> Decimal:
    return (Decimal(amount) * SHARE_DAYS / span_days).quantize(Decimal("0.01"))


def _periods(tariff, data_by_day, first_day) -> tuple[Period, ...]:
    """Finished periods of the tariff's length, as far back as the history is complete."""
    if first_day is None:
        return ()
    length = timedelta(days=tariff.validity_days)
    end = local_day(tariff.last_payment_at) - timedelta(days=1)
    found = []
    while len(found) < MAX_PERIODS:
        start = end - length + timedelta(days=1)
        if start < first_day:
            break
        used = sum(mb for day, mb in data_by_day.items() if start <= day <= end)
        found.append(Period(start, end, used, tariff.data_total_gb * MB_PER_GB))
        end = start - timedelta(days=1)
    return tuple(found)


def metrics(subscriber, now=None) -> Metrics | None:
    """The subscriber's figures, or None when there is no tariff to judge them against."""
    now = now or timezone.now()
    today = local_day(now)
    tariff = SubscriberTariff.objects.filter(subscriber=subscriber).first()
    if tariff is None:
        return None

    # Periods need history older than the profile window, so read further back for them.
    history = MAX_PERIODS * tariff.validity_days + PROFILE_DAYS
    days = list(
        DailyUsage.objects.filter(
            subscriber=subscriber, day__gt=today - timedelta(days=history), day__lte=today
        )
    )
    first_day = min((row.day for row in days), default=None)
    since = today - timedelta(days=PROFILE_DAYS - 1)
    recent = [row for row in days if row.day >= since]
    span_days = max(1, min(PROFILE_DAYS, (today - first_day).days + 1)) if first_day else 1

    apps_by_day: dict[date, dict[str, int]] = {}
    for row in AppUsage.objects.filter(subscriber=subscriber, day__gte=since, day__lte=today):
        apps_by_day.setdefault(row.day, {})[row.app] = row.data_mb
    month_start = today - timedelta(days=SHARE_DAYS - 1)
    by_app: dict[str, int] = {}
    by_app_profile: dict[str, int] = {}
    for day, apps in apps_by_day.items():
        for app, data_mb in apps.items():
            by_app_profile[app] = by_app_profile.get(app, 0) + data_mb
            if day >= month_start:
                by_app[app] = by_app.get(app, 0) + data_mb

    week_start = today - timedelta(days=BURN_DAYS - 1)
    roaming_start = today - timedelta(days=RECENT_ROAMING_DAYS - 1)
    today_row = next((row for row in recent if row.day == today), None)

    activations = PackActivation.objects.filter(
        subscriber=subscriber,
        kind__in=ADDON_KINDS,
        transaction__isnull=False,
        activated_at__gte=now - timedelta(days=PROFILE_DAYS),
    ).select_related("transaction")
    purchases = tuple(
        Purchase(row.kind, row.pack_id, -row.transaction.amount, row.activated_at)
        for row in activations.order_by("-activated_at", "-id")
    )

    return Metrics(
        now=now,
        today=today,
        tariff=tariff,
        balance=billing.balance_of(subscriber),
        next_price=tariffs.next_price(tariff),
        has_card=SavedCard.objects.filter(subscriber=subscriber).exists(),
        burn_mb_day=sum(row.data_mb for row in recent if row.day >= week_start) / BURN_DAYS,
        data_by_day={row.day: row.data_mb for row in days},
        apps_by_day=apps_by_day,
        by_app_mb=by_app,
        span_days=span_days,
        by_app_mb_month={
            app: data_mb * SHARE_DAYS / span_days for app, data_mb in by_app_profile.items()
        },
        minutes_month=sum(row.call_minutes for row in recent) * SHARE_DAYS / span_days,
        overage_mb_today=today_row.overage_mb if today_row else 0,
        overage_amount_today=today_row.overage_amount if today_row else ZERO,
        overage_amount_month=_monthly(sum((row.overage_amount for row in recent), ZERO), span_days),
        roaming_mb_recent=sum(row.roaming_data_mb for row in recent if row.day >= roaming_start),
        roaming_active=PackActivation.objects.filter(
            subscriber=subscriber, kind="roaming", status="active", expires_at__gt=now
        ).exists(),
        purchases=purchases,
        periods=_periods(tariff, {row.day: row.data_mb for row in days}, first_day),
    )
