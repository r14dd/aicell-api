"""Turns a usage profile into ranked recommendations.

Every number here is arithmetic over the catalogue and the profile; no model is
called. For each candidate the question is the same: what would the last 30
days have cost with it, and is that less than what the subscriber paid?

    projected = fee + price of the candidate
              + what stays uncovered, at the catalogue's out-of-package prices
              + roaming, as paid

A candidate is one change at a time: another tariff plan, the current plan plus
one pack, other roaming packs, or (on IsteSen) other slider values.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from math import ceil

from django.utils.translation import gettext as _

from api.common.formatting import money
from api.content import catalogue as content_catalogue
from api.packs import catalogue as packs_catalogue
from api.tariffs import catalogue as tariffs_catalogue
from api.tariffs import services as tariffs

from . import services, taxonomy
from .services import MB_PER_GB, Profile

WINDOW_DAYS = 30
MAX_RECOMMENDATIONS = 3
ZERO = Decimal("0")

# An app this dominant is named in the evidence; a category this big gets an insight.
EVIDENCE_APP_SHARE = 0.4
INSIGHT_CATEGORY_SHARE = 0.35
ISTESEN = "istesen"


@dataclass(frozen=True)
class Included:
    """What a setup covers in a month. None means unlimited."""

    data_mb: int | None
    minutes: int | None
    sms: int | None


@dataclass(frozen=True)
class Usage:
    """The month to price: data already reduced by what dedicated allowances cover."""

    data_mb: int
    minutes: int
    sms: int


@dataclass(frozen=True)
class Recommendation:
    kind: str  # tariff_plan | internet_pack | social_pack | roaming_pack | redesign
    target_id: str
    title: str
    current: Decimal
    projected: Decimal
    evidence: tuple[str, ...]
    action: dict
    plan_id: str | None = None
    values: dict | None = None
    quantity: int = 1

    @property
    def saving(self) -> Decimal:
        return self.current - self.projected


@dataclass(frozen=True)
class Insight:
    """A fact about a category of usage, with what can be sold for it (maybe nothing)."""

    category: str
    share: float
    text: str
    sells: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Result:
    profile: Profile
    current: Decimal
    recommendations: tuple[Recommendation, ...] = ()
    insights: tuple[Insight, ...] = field(default_factory=tuple)

    @property
    def fits(self) -> bool:
        """Nothing in the catalogue beats what the subscriber has."""
        return not self.recommendations


# --- arithmetic ---------------------------------------------------------------


def rates() -> dict[str, Decimal]:
    """Out-of-package prices per MB, minute and SMS."""
    listed = tariffs_catalogue.overage_rates()
    return {key: Decimal(listed.get(key, "0")) for key in ("data_mb", "minute", "sms")}


def overage(usage: Usage, included: Included) -> Decimal:
    """What usage beyond the included amounts costs at out-of-package prices."""
    price = rates()

    def beyond(used, limit):
        return ZERO if limit is None else Decimal(max(0, used - limit))

    return (
        beyond(usage.data_mb, included.data_mb) * price["data_mb"]
        + beyond(usage.minutes, included.minutes) * price["minute"]
        + beyond(usage.sms, included.sms) * price["sms"]
    )


def _messaging_covered(profile: Profile) -> int:
    """Messaging-app data the current tariff's messaging allowance pays for."""
    used = sum(profile.app_mb(app) for app in taxonomy.CATEGORIES["messaging"])
    allowance = profile.tariff.messaging_total_gb * MB_PER_GB if profile.tariff else 0
    return min(used, allowance)


def _current_included(profile: Profile) -> Included:
    tariff = profile.tariff
    if tariff is None:
        return Included(0, 0, 0)
    plan = next((p for p in tariffs_catalogue.plans() if p["id"] == tariff.plan_slug), None)
    return Included(
        data_mb=tariff.data_total_gb * MB_PER_GB,
        minutes=tariff.minutes_total,
        # The tariff record does not say how many SMS it includes; the catalogue
        # plan does. Without one (IsteSen) SMS are left out of the comparison.
        sms=plan["sms"] if plan else None,
    )


# --- candidates ---------------------------------------------------------------


def _navigate(to: str, label: str) -> dict:
    return {"action": "navigate", "to": to, "label": label}


def _tariff_plans(profile, current, evidence):
    usage = Usage(profile.data_mb, profile.minutes, profile.sms)
    for plan in tariffs_catalogue.plans():
        if plan["id"] == profile.tariff.plan_slug:
            continue
        included = Included(plan["data_mb"], plan["minutes"], plan["sms"])
        yield Recommendation(
            kind="tariff_plan",
            target_id=plan["id"],
            title=plan["title"],
            current=current,
            projected=Decimal(plan["price"])
            + overage(usage, included)
            + profile.spend.roaming_amount,
            evidence=evidence,
            action=_navigate(
                f"/tariffs/{plan['family_id']}?plan={plan['id']}", _("See the tariff")
            ),
        )


def _base(profile) -> tuple[Usage, Included, Decimal]:
    """Usage on the current tariff, what it includes, and the costs a pack would not change."""
    usage = Usage(profile.data_mb - _messaging_covered(profile), profile.minutes, profile.sms)
    fixed = profile.spend.tariff_fee + profile.spend.roaming_amount
    return usage, _current_included(profile), fixed


def _internet_packs(profile, current, evidence):
    usage, included, fixed = _base(profile)
    for pack in packs_catalogue.priced()["internet"]:
        if pack["data_mb"] is None:
            continue  # unlimited-by-the-hour packs cannot be compared with a month of usage
        with_pack = Included(included.data_mb + pack["data_mb"], included.minutes, included.sms)
        yield Recommendation(
            kind="internet_pack",
            target_id=pack["id"],
            title=pack["title"],
            current=current,
            projected=fixed + Decimal(pack["price"]) + overage(usage, with_pack),
            evidence=evidence,
            action=_navigate("/internet-packs", _("Open internet packs")),
        )


def _social_packs(profile, current, evidence):
    usage, included, fixed = _base(profile)
    for plan in packs_catalogue.priced()["social"]:
        app = taxonomy.SOCIAL_PACK_APP.get(plan["id"])
        if app is None or plan["days"] < WINDOW_DAYS or not profile.app_mb(app):
            continue  # only month-long plans of an app the subscriber actually uses
        covered = min(profile.app_mb(app), plan["data_mb"])
        remaining = Usage(usage.data_mb - covered, usage.minutes, usage.sms)
        yield Recommendation(
            kind="social_pack",
            target_id=plan["id"],
            plan_id=plan["plan_id"],
            title=plan["title"],
            current=current,
            projected=fixed + Decimal(plan["price"]) + overage(remaining, included),
            evidence=evidence,
            action=_navigate(f"/internet-packs/{plan['id']}", _("See the pack")),
        )


def _roaming_packs(profile, current, evidence):
    if not profile.roaming_data_mb:
        return
    at_home = current - profile.spend.roaming_amount
    for pack in packs_catalogue.priced()["roaming"]:
        if not pack["data_mb"]:
            continue
        quantity = ceil(profile.roaming_data_mb / pack["data_mb"])
        yield Recommendation(
            kind="roaming_pack",
            target_id=pack["id"],
            title=_("Roaming %(name)s") % {"name": pack["title"]},
            quantity=quantity,
            current=current,
            projected=at_home + quantity * Decimal(pack["price"]),
            evidence=evidence,
            action=_navigate("/sim/roaming", _("Open roaming packs")),
        )


def redesign_values(profile: Profile) -> dict[str, int]:
    """IsteSen slider values that match the usage, within each slider's range."""
    sliders = {slider["key"]: slider for slider in tariffs_catalogue.sliders()}

    def clamp(key, wanted):
        slider = sliders[key]
        stepped = ceil(wanted / slider["step"]) * slider["step"]
        return max(slider["min"], min(slider["max"], stepped))

    values = {}
    general_mb = profile.data_mb - _messaging_covered(profile)
    for key, app in taxonomy.SLIDER_APP.items():
        values[key] = clamp(key, ceil(profile.app_mb(app) / MB_PER_GB))
        general_mb -= min(profile.app_mb(app), values[key] * MB_PER_GB)
    values["internet"] = clamp("internet", ceil(max(0, general_mb) / MB_PER_GB))
    values["calls"] = clamp("calls", profile.minutes)
    return values


def _redesign(profile, current, evidence):
    if profile.tariff.family != ISTESEN:
        return
    values = redesign_values(profile)
    if all(profile.tariff.redesign.get(key) == value for key, value in values.items()):
        return  # already set this way
    covered_mb = sum(
        min(profile.app_mb(app), values[key] * MB_PER_GB)
        for key, app in taxonomy.SLIDER_APP.items()
    )
    remaining = Usage(
        profile.data_mb - _messaging_covered(profile) - covered_mb, profile.minutes, 0
    )
    included = Included(values["internet"] * MB_PER_GB, values["calls"], None)
    yield Recommendation(
        kind="redesign",
        target_id=ISTESEN,
        title=_("%(tariff)s, redesigned to your usage") % {"tariff": profile.tariff.title},
        values=values,
        current=current,
        projected=tariffs.estimate(values)
        + overage(remaining, included)
        + profile.spend.roaming_amount,
        evidence=evidence,
        action=_navigate("/my-tariff/redesign", _("Redesign my tariff")),
    )


# --- evidence and insights ----------------------------------------------------


def _gb(data_mb: int) -> str:
    return f"{data_mb / MB_PER_GB:.1f}"


def evidence_for(profile: Profile) -> tuple[str, ...]:
    """The facts behind a recommendation, each with its numbers."""
    facts = []
    spend = profile.spend
    if spend.addon_count:
        facts.append(
            _("%(count)s add-on packs, %(amount)s ₼")
            % {"count": spend.addon_count, "amount": money(spend.addon_amount)}
        )
    if profile.ran_out:
        facts.append(
            _("Included internet ran out on day %(day)s of %(days)s")
            % {"day": profile.ran_out.day, "days": profile.ran_out.period_days}
        )
    if profile.by_app and profile.share(profile.by_app[0][1]) >= EVIDENCE_APP_SHARE:
        app, data_mb = profile.by_app[0]
        facts.append(
            _("%(app)s %(share)s%% of data")
            % {"app": taxonomy.APP_LABELS[app], "share": round(profile.share(data_mb) * 100)}
        )
    if profile.tariff and profile.data_mb:
        facts.append(
            _("%(used)s GB used in %(days)s days, tariff includes %(included)s GB")
            % {
                "used": _gb(profile.data_mb),
                "days": profile.days,
                "included": profile.tariff.data_total_gb,
            }
        )
    if spend.roaming_count:
        facts.append(
            _("%(count)s roaming packs, %(amount)s ₼ for %(used)s GB abroad")
            % {
                "count": spend.roaming_count,
                "amount": money(spend.roaming_amount),
                "used": _gb(profile.roaming_data_mb),
            }
        )
    return tuple(facts)


def _sold(sells: taxonomy.Sells, profile: Profile) -> dict | None:
    """The catalogue item a `Sells` entry points at, if it exists for this subscriber."""
    if sells.kind == "social_pack":
        plans = [p for p in packs_catalogue.priced()["social"] if p["id"] == sells.target_id]
        if not plans:
            return None
        return {
            "kind": "social_pack",
            "target_id": sells.target_id,
            "title": plans[0]["pack_title"],
            "action": _navigate(f"/internet-packs/{sells.target_id}", _("See the pack")),
        }
    if sells.kind == "app_offer":
        offer = next(
            (o for o in content_catalogue.offers()["app"] if o["id"] == sells.target_id), None
        )
        return offer and {
            "kind": "app_offer",
            "target_id": offer["id"],
            "title": offer["name"],
            "action": _navigate("/offers/apps", _("See the offer")),
        }
    if sells.kind == "redesign":
        if not profile.tariff or profile.tariff.family != ISTESEN:
            return None
        return {
            "kind": "redesign",
            "target_id": ISTESEN,
            "title": _("Social network GB in your tariff"),
            "action": _navigate("/my-tariff/redesign", _("Redesign my tariff")),
        }
    if sells.kind == "tariff_messaging":
        if not profile.tariff or not profile.tariff.messaging_total_gb:
            return None
        return {
            "kind": "tariff_messaging",
            "target_id": "",
            "title": _("Your tariff's messaging allowance: %(gb)s GB")
            % {"gb": profile.tariff.messaging_total_gb},
            "action": _navigate("/remaining-balance", _("Open remaining balance")),
        }
    return None


def insights_for(profile: Profile) -> tuple[Insight, ...]:
    """The biggest category of data, with what can be sold for it. Never an invented product."""
    if not profile.by_category:
        return ()
    category, data_mb = profile.by_category[0]
    share = profile.share(data_mb)
    if share < INSIGHT_CATEGORY_SHARE:
        return ()
    sells = tuple(item for item in (_sold(s, profile) for s in taxonomy.SELLS[category]) if item)
    text = _("%(category)s: %(share)s%% of your data") % {
        "category": taxonomy.CATEGORY_LABELS[category],
        "share": round(share * 100),
    }
    return (Insight(category, share, text, sells),)


# --- the result ---------------------------------------------------------------


def _best_per_kind(candidates):
    best: dict[str, Recommendation] = {}
    for candidate in candidates:
        kept = best.get(candidate.kind)
        if kept is None or candidate.projected < kept.projected:
            best[candidate.kind] = candidate
    return list(best.values())


def recommend(subscriber, end=None) -> Result:
    """Ranked recommendations for the last 30 days, or an explicit "nothing beats this"."""
    profile = services.profile(subscriber, WINDOW_DAYS, end)
    current = profile.spend.plan_related
    insights = insights_for(profile)
    if profile.tariff is None:
        return Result(profile, current, (), insights)

    evidence = evidence_for(profile)
    candidates = _best_per_kind(
        candidate
        for build in (_tariff_plans, _internet_packs, _social_packs, _roaming_packs, _redesign)
        for candidate in build(profile, current, evidence)
    )
    cheaper = sorted(
        (c for c in candidates if c.saving > 0), key=lambda c: (-c.saving, c.projected)
    )
    if not cheaper and profile.ran_out:
        # Nothing is cheaper, but the included data did not last the period:
        # the least expensive option that covers the usage is worth showing.
        covering = [c for c in candidates if c.kind in ("tariff_plan", "internet_pack")]
        cheaper = sorted(covering, key=lambda c: c.projected)[:1]
    return Result(profile, current, tuple(cheaper[:MAX_RECOMMENDATIONS]), insights)
