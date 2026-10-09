"""The rules that find something worth telling a subscriber.

Each detector is a plain function of the subscriber's `Metrics` and a
`Catalogue` snapshot. It returns a `Finding` (the facts and the priced answers)
or None, reads nothing else and writes nothing. Thresholds are the constants
below; every price and saving is computed here, so whoever words the insight
has nothing left to calculate.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from math import ceil, floor

from django.utils import timezone

from api.kredit.models import KreditProduct
from api.tariffs import catalogue as tariffs_catalogue
from api.tariffs import services as tariffs

from . import advisor
from .catalogue import HOURS_PER_DAY, Catalogue, Option, per_gb_order
from .metrics import MB_PER_GB, SOCIAL_APP, VIDEO_APPS, Metrics, local_day

# --- thresholds ---------------------------------------------------------------
BIG_PACK_MB = 5 * MB_PER_GB  # a pack this size or larger is "high volume"
PACK_GONE_DAYS = 3  # ...and it is gone fast when it lasts no longer than this
VIDEO_SHARE = 0.6
REPEAT_PACKS = 2  # add-on packs in one tariff period
OVERAGE_MB = 20  # out-of-package megabytes today before it is urgent
FORECAST_USED_SHARE = 0.7  # the forecast is trusted once this much of the tariff is used
GAP_HEADROOM = 1.1
SOCIAL_SHARE = 0.4
TIKTOK_MB_MONTH = 4 * MB_PER_GB
APP_PACK_MIN_MB = MB_PER_GB  # an app's own pack is offered from this much a month
UNUSED_SHARE = 0.5
UNUSED_PERIODS = 3
UNUSED_HEADROOM = 1.1
RENEWAL_DAYS = 2
KREDIT_FOR_TOP_UP = "simkredit"
ZERO = Decimal("0")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Finding:
    kind: str
    evidence: dict
    offers: list[dict] = field(default_factory=list)
    severity: str = "info"
    recommended: int = 0


def money(amount) -> str:
    return f"{Decimal(amount):.2f}"


def gb(data_mb) -> float:
    return round(data_mb / MB_PER_GB, 1)


# --- offers -------------------------------------------------------------------


def _task(option: Option) -> dict:
    if option.kind == "social_pack":
        slug, _sep, plan = option.target_id.partition(":")
        return {"name": "activatePack", "params": {"slug": slug, "plan": plan}}
    if option.kind == "tariff_plan":
        return {"name": "changeTariff", "params": {"plan": option.target_id}}
    kind = "roaming" if option.kind == "roaming_pack" else "internet"
    return {"name": "buyPack", "params": {"kind": kind, "pack_id": option.target_id}}


def offer(option: Option, saving: Decimal | None = None) -> dict:
    """A catalogue item as an offer. Its label is added when it is shown, in the reader's language."""
    return {
        "ref": option.ref,
        "kind": option.kind,
        "target_id": option.target_id,
        "price": money(option.price),
        "hours": option.hours,
        "data_gb": gb(option.data_mb) if option.data_mb else None,
        "per_gb": money(option.per_gb) if option.per_gb is not None else None,
        "saving": money(saving) if saving is not None and saving > 0 else None,
        "task": _task(option),
    }


def redesign_offer(values: dict, price: Decimal, saving: Decimal) -> dict:
    return {
        "ref": "redesign",
        "kind": "redesign",
        "target_id": tariffs.ISTESEN,
        "price": money(price),
        "hours": None,
        "data_gb": float(sum(value for key, value in values.items() if key != "calls")),
        "per_gb": None,
        "saving": money(saving) if saving > 0 else None,
        "saving_year": money(saving * 12) if saving > 0 else None,
        "values": values,
        "task": {"name": "applyRedesign", "params": values},
    }


def _lasting(options: list[Option], need_mb: float, days: float) -> Option | None:
    """The cheapest option that holds `need_mb` and, if any does, also lasts `days`."""
    enough = [option for option in options if option.covers(need_mb)]
    lasting = [option for option in enough if option.hours >= days * HOURS_PER_DAY]
    return min(lasting or enough, key=lambda option: option.price, default=None)


def _cheaper_than(options: list[Option], chosen: Option) -> Option | None:
    """The most data that costs less than the chosen option: the budget alternative."""
    cheaper = [option for option in options if option.price < chosen.price]
    return max(cheaper, key=lambda option: (option.data_mb, -option.price), default=None)


# --- detectors ----------------------------------------------------------------


def video_heavy(m: Metrics, c: Catalogue) -> Finding | None:
    """A big general pack was used up in a few days, and most of the data is video."""
    if m.video_share < VIDEO_SHARE:
        return None
    for purchase in m.purchases:  # newest first
        pack = c.pack(purchase.pack_id) if purchase.kind == "internet" else None
        if pack is None or not pack.data_mb or pack.data_mb < BIG_PACK_MB:
            continue
        start = local_day(purchase.at)
        used, by_app = 0, {}
        for offset in range(PACK_GONE_DAYS):
            day = start + timedelta(days=offset)
            used += m.data_by_day.get(day, 0)
            for app, data_mb in m.apps_by_day.get(day, {}).items():
                by_app[app] = by_app.get(app, 0) + data_mb
            if used >= pack.data_mb:
                return _video_finding(m, c, pack, purchase, day, offset + 1, by_app)
    return None


def _video_finding(m, c, pack, purchase, emptied, days, by_app) -> Finding | None:
    offers = []
    for app in sorted(VIDEO_APPS, key=lambda app: -by_app.get(app, 0)):
        plan = c.plan_for(app, by_app.get(app, 0))
        if not by_app.get(app) or plan is None:
            continue
        # The same gigabytes cost this much inside the general pack that ran out.
        in_pack = (pack.per_gb * plan.data_mb / MB_PER_GB).quantize(CENT)
        offers.append(offer(plan, in_pack - plan.price) | {"same_gb_in_pack": money(in_pack)})
    if not offers:
        return None
    return Finding(
        "video_heavy",
        {
            "pack": {
                "id": pack.target_id,
                "data_gb": gb(pack.data_mb),
                "price": money(purchase.price),
                "per_gb": money(pack.per_gb),
                "activated_at": local_day(purchase.at).isoformat(),
                "emptied_at": emptied.isoformat(),
                "days": days,
            },
            "by_app_gb": {app: gb(data_mb) for app, data_mb in sorted(by_app.items())},
            "video_share": round(m.video_share, 2),
        },
        offers,
    )


def repeat_packs(m: Metrics, c: Catalogue) -> Finding | None:
    """Several add-on packs in one period: a bigger tariff may cost less than the sum."""
    bought = m.period_purchases
    if len(bought) < REPEAT_PACKS:
        return None
    plans = sorted(
        (
            plan
            for plan in c.plans
            if plan.target_id != m.tariff.plan_slug and plan.covers(m.data_mb_month)
        ),
        key=lambda plan: plan.price,
    )
    if not plans:
        return None
    spend = m.monthly_spend
    return Finding(
        "repeat_packs",
        {
            "packs": [
                {
                    "id": purchase.pack_id,
                    "kind": purchase.kind,
                    "price": money(purchase.price),
                    "date": local_day(purchase.at).isoformat(),
                }
                for purchase in bought
            ],
            "packs_total": money(sum((purchase.price for purchase in bought), ZERO)),
            "tariff_price": money(m.tariff.price),
            "monthly_spend": money(spend),
            "data_gb_month": gb(m.data_mb_month),
        },
        [offer(plan, spend - plan.price) for plan in plans[:2]],
    )


def overage(m: Metrics, c: Catalogue) -> Finding | None:
    """The tariff's internet is gone and traffic is being charged per megabyte right now."""
    if m.remaining_mb > 0 or m.days_left <= 1 or m.overage_mb_today <= OVERAGE_MB:
        return None
    sized = c.sized_internet()
    day_at_rate = (Decimal(m.burn_mb_day) * c.overage_per_mb).quantize(CENT)
    today = min(
        (option for option in sized if option.hours <= HOURS_PER_DAY),
        key=lambda option: option.price,
        default=None,
    )
    rest = _lasting(sized, m.burn_mb_day * m.days_left, m.days_left)
    offers = []
    if today:
        offers.append(offer(today, day_at_rate - today.price))
    if rest and rest != today:
        offers.append(offer(rest, day_at_rate * ceil(m.days_left) - rest.price))
    if not offers:
        return None
    return Finding(
        "overage",
        {
            "overage_mb": m.overage_mb_today,
            "overage_amount": money(m.overage_amount_today),
            "rate_per_mb": money(c.overage_per_mb),
            "burn_gb_day": gb(m.burn_mb_day),
            "days_left": ceil(m.days_left),
        },
        offers,
        severity="urgent",
    )


def forecast_gap(m: Metrics, c: Catalogue) -> Finding | None:
    """At the current rate the internet runs out before the renewal."""
    if m.remaining_mb <= 0 or m.gap_mb <= 0 or m.used_share < FORECAST_USED_SHARE:
        return None
    sized = c.sized_internet()
    need_mb = m.gap_mb * GAP_HEADROOM
    days_short = m.days_left - m.days_to_empty
    chosen = _lasting(sized, need_mb, days_short) or max(
        sized, key=lambda option: option.data_mb, default=None
    )
    if chosen is None:
        return None
    offers = [offer(chosen)]
    budget = _cheaper_than(sized, chosen)
    if budget:
        offers.append(offer(budget))
    return Finding(
        "forecast_gap",
        {
            "remaining_gb": gb(m.remaining_mb),
            "days_left": ceil(m.days_left),
            "burn_gb_day": gb(m.burn_mb_day),
            "empty_on": (m.today + timedelta(days=floor(m.days_to_empty))).isoformat(),
            "gap_gb": gb(m.gap_mb),
            "need_gb": gb(need_mb),
        },
        offers,
    )


def social_heavy(m: Metrics, c: Catalogue) -> Finding | None:
    """Much of the data goes to social apps that have cheaper gigabytes of their own."""
    tiktok_mb = m.by_app_mb_month.get("tiktok", 0)
    if m.social_share < SOCIAL_SHARE and tiktok_mb < TIKTOK_MB_MONTH:
        return None
    offers = []
    if m.tariff.family == tariffs.ISTESEN:
        values, _covered = advisor.redesign_for(m)
        if values != {key: m.tariff.redesign.get(key) for key in values}:
            price = tariffs.estimate(values)
            offers.append(redesign_offer(values, price, advisor.current_total(m) - price))
    for app in sorted((SOCIAL_APP, "tiktok"), key=lambda app: -m.by_app_mb_month.get(app, 0)):
        used_mb = m.by_app_mb_month.get(app, 0)
        plan = c.plan_for(app, used_mb) if used_mb >= APP_PACK_MIN_MB else None
        if plan:
            offers.append(offer(plan))
    if not offers:
        return None
    return Finding(
        "social_heavy",
        {
            "by_app_gb": {app: gb(data_mb) for app, data_mb in sorted(m.by_app_mb_month.items())},
            "social_share": round(m.social_share, 2),
            "tiktok_gb_month": gb(tiktok_mb),
        },
        offers,
    )


def underused(m: Metrics, c: Catalogue) -> Finding | None:
    """Half of the tariff's internet or more was left over, three periods running."""
    periods = m.periods[:UNUSED_PERIODS]
    if len(periods) < UNUSED_PERIODS or any(p.unused_share < UNUSED_SHARE for p in periods):
        return None
    most_used_mb = max(period.used_mb for period in periods)
    need_mb = most_used_mb * UNUSED_HEADROOM
    offers = []
    if m.tariff.family == tariffs.ISTESEN:
        sliders = {slider["key"]: slider for slider in tariffs_catalogue.sliders()}
        slider = sliders.get("internet")
        if slider:
            stepped = ceil(need_mb / MB_PER_GB / slider["step"]) * slider["step"]
            internet = max(slider["min"], min(slider["max"], stepped))
            values = {key: m.tariff.redesign.get(key, sliders[key]["min"]) for key in sliders}
            if internet < values["internet"]:
                values["internet"] = internet
                price = tariffs.estimate(values)
                offers.append(redesign_offer(values, price, m.next_price - price))
    cheaper = [
        plan
        for plan in c.plans
        if plan.covers(need_mb)
        and plan.price < m.next_price
        and plan.target_id != m.tariff.plan_slug
    ]
    if cheaper:
        plan = min(cheaper, key=lambda plan: plan.price)
        offers.append(offer(plan, m.next_price - plan.price))
    if not offers:
        return None
    return Finding(
        "underused",
        {
            "included_gb": gb(periods[0].included_mb),
            "periods": [
                {
                    "start": period.start.isoformat(),
                    "end": period.end.isoformat(),
                    "used_gb": gb(period.used_mb),
                    "unused_gb": gb(period.unused_mb),
                }
                for period in periods
            ],
        },
        offers,
    )


def roaming(m: Metrics, c: Catalogue) -> Finding | None:
    """Data is being used abroad without a roaming pack."""
    if not m.roaming_mb_recent or m.roaming_active:
        return None
    packs = sorted(c.sold(c.roaming), key=per_gb_order)
    if not packs:
        return None
    return Finding(
        "roaming",
        {"roaming_mb": m.roaming_mb_recent, "days": 3},
        [offer(pack) for pack in packs[:2]],
    )


def renewal_shortfall(m: Metrics, c: Catalogue) -> Finding | None:
    """The tariff renews within two days and the balance does not cover it."""
    shortfall = m.renewal_shortfall
    if m.days_left > RENEWAL_DAYS or shortfall <= 0:
        return None
    amount = money(ceil(shortfall))
    offers = [
        {
            "ref": "top_up",
            "kind": "top_up",
            "target_id": "",
            "price": amount,
            "task": {"name": "topUp", "params": {"amount": amount}},
        }
    ]
    kredit = None
    if not m.has_card:
        kredit = KreditProduct.objects.active().filter(slug=KREDIT_FOR_TOP_UP).first()
    if kredit:
        offers.append(
            {
                "ref": f"kredit:{kredit.slug}",
                "kind": "kredit",
                "target_id": kredit.slug,
                "price": money(kredit.fee),
                "task": {"name": "takeKredit", "params": {"slug": kredit.slug}},
            }
        )
    return Finding(
        "renewal_shortfall",
        {
            "balance": money(m.balance),
            "price": money(m.next_price),
            "shortfall": money(shortfall),
            "renews_at": timezone.localtime(m.tariff.next_payment_at).isoformat(timespec="seconds"),
            "has_card": m.has_card,
        },
        offers,
        severity="urgent",
    )


# Urgent ones first; within a severity, the more specific finding before the general one.
DETECTORS = (
    overage,
    renewal_shortfall,
    video_heavy,
    repeat_packs,
    forecast_gap,
    social_heavy,
    underused,
    roaming,
)


def detect(m: Metrics, c: Catalogue) -> list[Finding]:
    return [finding for detector in DETECTORS if (finding := detector(m, c)) is not None]
