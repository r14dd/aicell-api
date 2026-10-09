"""Finds what the usage says and keeps the subscriber's insights.

Every number is arithmetic over the profile and the catalogue; no model is involved.
A detector returns one `Found` or nothing. Its offers carry the task the app runs
(`task.name` is one of Laya's), so the app never has to work out what to do.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from math import ceil

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from api.billing import services as billing
from api.common.exceptions import InsightClosed, NotFound
from api.common.formatting import money
from api.packs import catalogue as packs_catalogue
from api.tariffs import catalogue as tariffs_catalogue
from api.tariffs import services as tariffs
from api.usage import recommendations, taxonomy
from api.usage import services as usage
from api.usage.models import DailyUsage

from .models import Insight

COOLDOWN_DAYS = 7
SHORTFALL_DAYS = 2  # tell the subscriber this close to the renewal
FORECAST_MIN_DAYS = 3  # days of the period needed before the pace means anything
UNDERUSED_SHARE = 0.6  # used less than this much of the included data
MIN_SAVING = Decimal("1")
ISTESEN = recommendations.ISTESEN

# Most urgent first: this is the order the app gets them in.
ORDER = (
    "renewal_shortfall",
    "overage",
    "forecast_gap",
    "repeat_packs",
    "roaming",
    "social_heavy",
    "underused",
    "video_heavy",
)


@dataclass(frozen=True)
class Found:
    kind: str
    evidence: dict
    offers: list[dict]


def _gb(data_mb) -> float:
    return round(data_mb / usage.MB_PER_GB, 1)


def _offer(title, price, name, params, **extra) -> dict:
    return {
        "title": title,
        "price": money(price),
        "task": {"name": name, "params": params},
        **extra,
    }


def _pack_offer(pack) -> dict:
    return _offer(pack["title"], pack["price"], "buyPack", {"pack_id": pack["id"]})


def _cheapest_pack(profile, need_mb=0) -> dict | None:
    """The cheapest internet pack with at least `need_mb`, or the biggest one if none is."""
    packs = [p for p in packs_catalogue.priced()["internet"] if p["data_mb"]]
    big_enough = [p for p in packs if p["data_mb"] >= need_mb]
    if big_enough:
        return min(big_enough, key=lambda p: Decimal(p["price"]))
    return max(packs, key=lambda p: p["data_mb"], default=None)


def _best(options, kind, target_id=None):
    chosen = [o for o in options if o.kind == kind and target_id in (None, o.target_id)]
    return min(chosen, key=lambda o: o.projected, default=None)


def _plan_offer(rec) -> dict:
    plan = next(p for p in tariffs_catalogue.plans() if p["id"] == rec.target_id)
    return _offer(rec.title, plan["price"], "changeTariff", {"plan": rec.target_id})


def _redesign_offer(rec) -> dict:
    return _offer(rec.title, tariffs.estimate(rec.values), "applyRedesign", dict(rec.values))


# --- detectors ----------------------------------------------------------------
# Each takes (subscriber, profile, options, today) and returns Found or None.


def renewal_shortfall(subscriber, profile, options, today):
    tariff = profile.tariff
    renews = timezone.localtime(tariff.next_payment_at).date()
    balance = billing.balance_of(subscriber)
    short = tariff.price - balance
    days_left = (renews - today).days
    if short <= 0 or not 0 <= days_left <= SHORTFALL_DAYS:
        return None
    amount = ceil(short)
    return Found(
        "renewal_shortfall",
        {
            "price": money(tariff.price),
            "balance": money(balance),
            "shortfall": money(short),
            "renews_on": renews.isoformat(),
            "days_left": days_left,
        },
        [
            _offer(
                _("Top up %(amount)s ₼") % {"amount": amount}, amount, "topUp", {"amount": amount}
            )
        ],
    )


def overage(subscriber, profile, options, today):
    tariff = profile.tariff
    if profile.ran_out is None:
        return None
    pack = _cheapest_pack(profile)
    if pack is None:
        return None
    return Found(
        "overage",
        {
            "included_gb": tariff.data_total_gb,
            "ran_out_day": profile.ran_out.day,
            "period_days": profile.ran_out.period_days,
            "price_per_mb": money(recommendations.rates()["data_mb"]),
        },
        [_pack_offer(pack)],
    )


def forecast_gap(subscriber, profile, options, today):
    tariff = profile.tariff
    if profile.ran_out is not None:
        return None
    started = timezone.localtime(tariff.last_payment_at).date()
    renews = timezone.localtime(tariff.next_payment_at).date()
    elapsed = (today - started).days + 1
    used = (
        DailyUsage.objects.filter(
            subscriber=subscriber, day__gte=started, day__lte=today
        ).aggregate(total=Sum("data_mb"))["total"]
        or 0
    )
    if elapsed < FORECAST_MIN_DAYS or not used:
        return None
    pace = used / elapsed  # MB a day
    left_mb = tariff.data_total_gb * usage.MB_PER_GB - used
    days_to_empty = left_mb / pace
    days_to_renewal = (renews - today).days
    if days_to_empty >= days_to_renewal:
        return None
    gap_mb = pace * days_to_renewal - left_mb
    pack = _cheapest_pack(profile, ceil(gap_mb))
    if pack is None:
        return None
    return Found(
        "forecast_gap",
        {
            "runs_out_on": (today + timedelta(days=int(days_to_empty))).isoformat(),
            "renews_on": renews.isoformat(),
            "gap_gb": _gb(gap_mb),
            "daily_gb": _gb(pace),
        },
        [_pack_offer(pack)],
    )


def repeat_packs(subscriber, profile, options, today):
    if profile.spend.addon_count < usage.HEAVY_ADDON_PURCHASES:
        return None
    best = _best(options, "tariff_plan")
    if best is None or best.saving < MIN_SAVING:
        return None
    return Found(
        "repeat_packs",
        {
            "packs": profile.spend.addon_count,
            "paid": money(profile.spend.addon_amount),
            "data_gb": _gb(profile.data_mb),
            "days": profile.days,
            "saving_month": money(best.saving),
        },
        [_plan_offer(best)],
    )


def roaming(subscriber, profile, options, today):
    if not (profile.roaming_days and profile.roaming_data_mb):
        return None
    best = _best(options, "roaming_pack")
    if best is None or best.saving <= 0:
        return None
    pack = next(p for p in packs_catalogue.priced()["roaming"] if p["id"] == best.target_id)
    return Found(
        "roaming",
        {
            "roaming_gb": _gb(profile.roaming_data_mb),
            "roaming_days": profile.roaming_days,
            "paid": money(profile.spend.roaming_amount),
            "saving": money(best.saving),
        },
        [_offer(best.title, pack["price"], "buyPack", {"pack_id": pack["id"]})],
    )


def _social_share(profile) -> float:
    return profile.share(sum(profile.app_mb(app) for app in taxonomy.CATEGORIES["social"]))


def social_heavy(subscriber, profile, options, today):
    best = _best(options, "redesign")
    if best is None or _social_share(profile) < recommendations.INSIGHT_CATEGORY_SHARE:
        return None
    return Found(
        "social_heavy",
        {
            "tiktok_gb": _gb(profile.app_mb("tiktok")),
            "instagram_gb": _gb(profile.app_mb("instagram_facebook")),
            "days": profile.days,
            "price": money(tariffs.estimate(best.values)),
        },
        [_redesign_offer(best)],
    )


def underused(subscriber, profile, options, today):
    best = _best(options, "redesign")
    included_mb = profile.tariff.data_total_gb * usage.MB_PER_GB
    if best is None or best.saving < MIN_SAVING or profile.data_mb >= included_mb * UNDERUSED_SHARE:
        return None
    return Found(
        "underused",
        {
            "used_gb": _gb(profile.data_mb),
            "included_gb": profile.tariff.data_total_gb,
            "days": profile.days,
            "saving_month": money(best.saving),
            "saving_year": money(best.saving * 12),
        },
        [_redesign_offer(best)],
    )


def video_heavy(subscriber, profile, options, today):
    video_mb = sum(profile.app_mb(app) for app in taxonomy.CATEGORIES["video"])
    best = _best(options, "social_pack", "youtube")
    if best is None or profile.share(video_mb) < recommendations.INSIGHT_CATEGORY_SHARE:
        return None
    plan = next(
        p
        for p in packs_catalogue.priced()["social"]
        if p["id"] == best.target_id and p["plan_id"] == best.plan_id
    )
    evidence = {
        "youtube_gb": _gb(profile.app_mb("youtube")),
        "share": round(profile.share(video_mb) * 100),
        "days": profile.days,
        "pack_gb": _gb(plan["data_mb"]) if plan["data_mb"] else None,
        "pack_price": plan["price"],
    }
    if profile.ran_out:
        evidence["ran_out_day"] = profile.ran_out.day
    offer = _offer(
        best.title, plan["price"], "activatePack", {"slug": best.target_id, "plan": best.plan_id}
    )
    return Found("video_heavy", evidence, [offer])


DETECTORS = (
    renewal_shortfall,
    overage,
    forecast_gap,
    repeat_packs,
    roaming,
    social_heavy,
    underused,
    video_heavy,
)


def detect(subscriber) -> list[Found]:
    """What applies to the subscriber right now, most urgent first."""
    result = recommendations.recommend(subscriber)
    profile = result.profile
    if profile.tariff is None:
        return []
    options = recommendations.candidates_for(profile, result.current)
    today = profile.end
    found = {}
    for detector in DETECTORS:
        item = detector(subscriber, profile, options, today)
        if item:
            found[item.kind] = item
    if "social_heavy" in found:
        found.pop("underused", None)  # the same redesign, said once
    return [found[kind] for kind in ORDER if kind in found]


# --- the subscriber's insights --------------------------------------------------


@transaction.atomic
def refresh(subscriber, now=None) -> list[Insight]:
    """Bring the stored insights up to date and return the open ones, most urgent first."""
    now = now or timezone.now()
    billing.lock_wallet(subscriber)  # one refresh at a time per subscriber
    rows = {row.kind: row for row in Insight.objects.filter(subscriber=subscriber)}
    open_rows = []
    for item in detect(subscriber):
        row = rows.get(item.kind)
        if row is None:
            row = Insight(subscriber=subscriber, kind=item.kind, created_at=now)
        elif row.status not in Insight.OPEN:
            if now - row.decided_at < timedelta(days=COOLDOWN_DAYS):
                continue
            row.status, row.decided_at = "new", None
        row.evidence, row.offers, row.recommended = item.evidence, item.offers, 0
        row.save()
        open_rows.append(row)
    return open_rows


def _own_open(subscriber, insight_id) -> Insight:
    """The subscriber's own insight, still open. Someone else's is simply not found."""
    row = Insight.objects.filter(subscriber=subscriber, id=insight_id).first()
    if row is None:
        raise NotFound()
    if row.status not in Insight.OPEN:
        raise InsightClosed()
    return row


def seen(subscriber, insight_id) -> Insight:
    row = _own_open(subscriber, insight_id)
    if row.status == "new":
        row.status = "seen"
        row.save(update_fields=["status"])
    return row


def decide(subscriber, insight_id, status) -> Insight:
    """Close the insight as `accepted` or `dismissed`."""
    row = _own_open(subscriber, insight_id)
    row.status = status
    row.decided_at = timezone.now()
    row.save(update_fields=["status", "decided_at"])
    return row


# --- the tariff advisor ---------------------------------------------------------


def advise(subscriber) -> dict:
    """The current setup against the tariffs and redesign that would have cost less."""
    result = recommendations.recommend(subscriber)
    profile = result.profile
    tariff = profile.tariff
    if tariff is None:
        raise NotFound()
    candidates = []
    for rec in result.recommendations:
        if rec.kind == "tariff_plan":
            candidates.append((rec, _plan_offer(rec)))
        elif rec.kind == "redesign":
            candidates.append((rec, _redesign_offer(rec)))
    return {
        "current": {
            "plan": tariff.plan_slug or tariff.family,
            "title": tariff.title,
            "monthly_cost": money(result.current),
        },
        "candidates": [
            {
                "id": "redesign" if rec.kind == "redesign" else rec.target_id,
                "title": rec.title,
                "monthly_cost": money(rec.projected),
                "saving_month": money(rec.saving),
                "task": offer["task"],
            }
            for rec, offer in candidates
        ],
        "recommended": (
            ("redesign" if candidates[0][0].kind == "redesign" else candidates[0][0].target_id)
            if candidates
            else "current"
        ),
        "effective_from": timezone.localtime(tariff.next_payment_at).date().isoformat(),
    }
