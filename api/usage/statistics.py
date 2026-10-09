"""Usage figures across all subscribers, for the admin's statistics page.

Every figure is one aggregation in the database: nothing here loads rows per
subscriber, so the cost does not grow with the number of subscribers shown.
Segments and recommendations come from the stored `SubscriberInsight` rows.

A period is whole days in Asia/Baku ending today; the one before it has the
same length and ends the day before this one starts.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, Exists, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from api.packs.models import PackActivation
from api.users.models import Subscriber

from . import services, taxonomy
from .models import SEGMENTS, AppUsage, DailyUsage, PersonalOffer, SubscriberInsight

PERIODS = (7, 30, 90)
DEFAULT_PERIOD = 30
LINE_TYPES = tuple(key for key, _label in Subscriber.LINE_TYPES)
SEGMENT_KEYS = tuple(key for key, _label in SEGMENTS)
SORTS = {"data": "-data_mb", "minutes": "-minutes", "addon": "-addon_spend"}
ZERO = Decimal("0")
MONEY = DecimalField(max_digits=12, decimal_places=2)


def gb(data_mb) -> Decimal:
    """Megabytes as gigabytes. The only place the conversion is made."""
    return (Decimal(data_mb or 0) / services.MB_PER_GB).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class Filters:
    """What the page is narrowed to. An empty string means "all"."""

    days: int = DEFAULT_PERIOD
    segment: str = ""
    line_type: str = ""

    def subscribers(self, prefix: str = "") -> dict:
        """Lookups that pick the matching subscribers, from a model that points at one."""
        lookups = {f"{prefix}is_staff": False}
        if self.segment:
            lookups[f"{prefix}insight__segment"] = self.segment
        if self.line_type:
            lookups[f"{prefix}line_type"] = self.line_type
        return lookups


@dataclass(frozen=True)
class Window:
    """Whole days, first and last included."""

    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def previous(self) -> "Window":
        return Window(self.start - timedelta(days=self.days), self.start - timedelta(days=1))

    @property
    def moments(self) -> tuple[datetime, datetime]:
        """The same days as moments in Asia/Baku: from midnight to before the next midnight."""
        zone = timezone.get_default_timezone()
        start = datetime.combine(self.start, time.min, tzinfo=zone)
        return start, datetime.combine(self.end + timedelta(days=1), time.min, tzinfo=zone)

    def each_day(self) -> list[date]:
        return [self.start + timedelta(days=offset) for offset in range(self.days)]


def window(days: int, end: date | None = None) -> Window:
    end = end or services.today()
    return Window(end - timedelta(days=days - 1), end)


# --- headline -----------------------------------------------------------------


@dataclass(frozen=True)
class Totals:
    active: int = 0  # subscribers who used anything
    data_mb: int = 0
    minutes: int = 0
    sms: int = 0
    roaming_data_mb: int = 0
    roamers: int = 0
    addon_revenue: Decimal = ZERO
    addon_count: int = 0

    def per_subscriber(self, amount) -> Decimal:
        return Decimal(amount) / self.active if self.active else ZERO


USED_SOMETHING = (
    Q(data_mb__gt=0)
    | Q(call_minutes__gt=0)
    | Q(sms__gt=0)
    | Q(roaming_data_mb__gt=0)
    | Q(roaming_minutes__gt=0)
)
ROAMED = Q(roaming_data_mb__gt=0) | Q(roaming_minutes__gt=0)


def _usage(filters: Filters, span: Window):
    return DailyUsage.objects.filter(
        day__gte=span.start, day__lte=span.end, **filters.subscribers("subscriber__")
    )


def _addons(filters: Filters, span: Window):
    """Add-on packs (internet and social) paid for in the window."""
    start, end = span.moments
    return PackActivation.objects.filter(
        kind__in=services.ADDON_KINDS,
        transaction__created_at__gte=start,
        transaction__created_at__lt=end,
        **filters.subscribers("subscriber__"),
    )


def totals(filters: Filters, span: Window) -> Totals:
    # The names differ from the columns: a filter below must mean the column, not a sum.
    used = _usage(filters, span).aggregate(
        active=Count("subscriber", distinct=True, filter=USED_SOMETHING),
        roamers=Count("subscriber", distinct=True, filter=ROAMED),
        all_data=Sum("data_mb"),
        all_minutes=Sum("call_minutes"),
        all_sms=Sum("sms"),
        all_roaming=Sum("roaming_data_mb"),
    )
    sold = _addons(filters, span).aggregate(
        revenue=Sum(-F("transaction__amount"), output_field=MONEY), count=Count("id")
    )
    return Totals(
        active=used["active"],
        data_mb=used["all_data"] or 0,
        minutes=used["all_minutes"] or 0,
        sms=used["all_sms"] or 0,
        roaming_data_mb=used["all_roaming"] or 0,
        roamers=used["roamers"],
        addon_revenue=Decimal(sold["revenue"] or 0).quantize(services.CENT),
        addon_count=sold["count"],
    )


def change(now, before) -> float | None:
    """How much `now` differs from `before`, as a fraction. None when there is no "before"."""
    if not before:
        return None
    return float((Decimal(now) - Decimal(before)) / Decimal(before))


@dataclass(frozen=True)
class Headline:
    window: Window
    now: Totals
    before: Totals

    def change(self, name: str) -> float | None:
        return change(getattr(self.now, name), getattr(self.before, name))


def headline(filters: Filters, end: date | None = None) -> Headline:
    span = window(filters.days, end)
    return Headline(span, totals(filters, span), totals(filters, span.previous))


# --- trend --------------------------------------------------------------------


@dataclass(frozen=True)
class TrendDay:
    day: date
    data_mb: int
    minutes: int


def trend(filters: Filters, end: date | None = None) -> list[TrendDay]:
    """Data and call minutes for every day of the period, days without usage included."""
    span = window(filters.days, end)
    rows = {
        row["day"]: row
        for row in _usage(filters, span)
        .values("day")
        .annotate(data=Sum("data_mb"), minutes=Sum("call_minutes"))
    }
    empty = {"data": 0, "minutes": 0}
    return [
        TrendDay(day, rows.get(day, empty)["data"], rows.get(day, empty)["minutes"])
        for day in span.each_day()
    ]


# --- categories ---------------------------------------------------------------


@dataclass(frozen=True)
class Share:
    key: str
    data_mb: int
    share: float  # of the whole it belongs to, 0..1


@dataclass(frozen=True)
class Category(Share):
    apps: tuple[Share, ...] = ()


def _share(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def categories(filters: Filters, end: date | None = None) -> list[Category]:
    """Data per category, every category listed, each with its apps."""
    span = window(filters.days, end)
    by_app = dict(
        AppUsage.objects.filter(
            day__gte=span.start, day__lte=span.end, **filters.subscribers("subscriber__")
        )
        .values("app")
        .annotate(total=Sum("data_mb"))
        .values_list("app", "total")
    )
    whole = sum(by_app.values())
    result = []
    for key, apps in taxonomy.CATEGORIES.items():
        data_mb = sum(by_app.get(app, 0) for app in apps)
        shares = sorted(
            (Share(app, by_app.get(app, 0), _share(by_app.get(app, 0), data_mb)) for app in apps),
            key=lambda share: -share.data_mb,
        )
        result.append(Category(key, data_mb, _share(data_mb, whole), tuple(shares)))
    return result


# --- segments -----------------------------------------------------------------


@dataclass(frozen=True)
class Segment:
    key: str
    subscribers: int = 0
    data_mb: float = 0  # the three averages are per subscriber, over the last 30 days
    minutes: float = 0
    spend: Decimal = ZERO


def segments(filters: Filters) -> list[Segment]:
    """Every segment with its size and averages, from the stored insights."""
    rows = {
        row["segment"]: row
        for row in SubscriberInsight.objects.filter(**filters.subscribers("subscriber__"))
        .values("segment")
        .annotate(
            subscribers=Count("id"),
            avg_data=Avg("data_mb"),
            avg_minutes=Avg("minutes"),
            avg_spend=Avg("spend"),
        )
    }
    return [
        Segment(
            key,
            rows[key]["subscribers"],
            float(rows[key]["avg_data"]),
            float(rows[key]["avg_minutes"]),
            Decimal(rows[key]["avg_spend"]).quantize(services.CENT),
        )
        if key in rows
        else Segment(key)
        for key in SEGMENT_KEYS
    ]


# --- sales --------------------------------------------------------------------


@dataclass(frozen=True)
class Sales:
    open: int = 0
    accepted: int = 0
    declined: int = 0
    expired: int = 0
    can_save: int = 0  # subscribers whose top recommendation is cheaper than what they pay
    saving: Decimal = ZERO  # what those recommendations would save, per month

    @property
    def acceptance(self) -> float | None:
        """Accepted out of the offers that got an answer; None when none did."""
        answered = self.accepted + self.declined
        return self.accepted / answered if answered else None


def sales(filters: Filters, end: date | None = None) -> Sales:
    """Personal offers made in the period by outcome, and the saving on the table today."""
    start, stop = window(filters.days, end).moments
    offers = PersonalOffer.objects.filter(
        created_at__gte=start, created_at__lt=stop, **filters.subscribers("subscriber__")
    ).aggregate(
        open=Count("id", filter=Q(status__in=PersonalOffer.OPEN)),
        accepted=Count("id", filter=Q(status="accepted")),
        declined=Count("id", filter=Q(status="declined")),
        expired=Count("id", filter=Q(status="expired")),
    )
    saving = SubscriberInsight.objects.filter(
        saving__gt=0, **filters.subscribers("subscriber__")
    ).aggregate(can_save=Count("id"), total=Sum("saving"))
    return Sales(**offers, can_save=saving["can_save"], saving=saving["total"] or ZERO)


# --- top subscribers ----------------------------------------------------------


def _total(rows, field, output=None):
    """A subscriber's sum over `rows`, as a column on the subscriber query."""
    summed = rows.filter(subscriber=OuterRef("pk")).values("subscriber")
    return Coalesce(
        Subquery(summed.annotate(total=Sum(field, output_field=output)).values("total")[:1]),
        0,
        output_field=output,
    )


def top_subscribers(filters: Filters, sort: str = "data", end: date | None = None):
    """Subscribers who have usage rows in the period, biggest first by `sort`.

    A query set of dicts (`id`, `msisdn`, `segment`, `data_mb`, `minutes`,
    `addon_spend`), left unevaluated so the caller can take one page of it.
    """
    span = window(filters.days, end)
    used = DailyUsage.objects.filter(day__gte=span.start, day__lte=span.end)
    bought = _addons(Filters(), span)
    return (
        Subscriber.objects.filter(
            Exists(used.filter(subscriber=OuterRef("pk"))), **filters.subscribers()
        )
        .annotate(
            data_mb=_total(used, "data_mb"),
            minutes=_total(used, "call_minutes"),
            addon_spend=_total(bought, -F("transaction__amount"), MONEY),
            segment=F("insight__segment"),
        )
        .order_by(SORTS.get(sort, SORTS["data"]), "msisdn")
        .values("id", "msisdn", "segment", "data_mb", "minutes", "addon_spend")
    )


def top_categories(subscriber_ids, filters: Filters, end: date | None = None) -> dict[int, str]:
    """The category each of the given subscribers used most data on, in the period."""
    span = window(filters.days, end)
    rows = (
        AppUsage.objects.filter(
            subscriber__in=subscriber_ids, day__gte=span.start, day__lte=span.end
        )
        .values("subscriber", "app")
        .annotate(total=Sum("data_mb"))
    )
    used: dict[int, dict[str, int]] = {}
    for row in rows:  # at most one row per app for each subscriber on the page
        per_category = used.setdefault(row["subscriber"], {})
        category = taxonomy.category_of(row["app"])
        per_category[category] = per_category.get(category, 0) + row["total"]
    return {
        subscriber: max(per_category, key=per_category.get)
        for subscriber, per_category in used.items()
        if any(per_category.values())
    }
