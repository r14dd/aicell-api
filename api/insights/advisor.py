"""Which tariff setup would have cost the least for the way the subscriber uses the number.

"IsteSen+" is not a new tariff: it is the IsteSen constructor with slider
values worked out from the usage, priced by the same formula the app uses.
It is compared with the cheapest catalogue plan that covers the usage; the
candidate with the lowest monthly total wins.
"""

from decimal import Decimal
from math import ceil

from api.tariffs import catalogue as tariffs_catalogue
from api.tariffs import services as tariffs
from api.usage import taxonomy

from .catalogue import Catalogue, Option
from .metrics import MB_PER_GB, Metrics, local_day

ISTESEN_PLUS = "istesen-plus"
GENERAL_HEADROOM = 1.3  # general internet is set this much above what was used
MESSAGING_MB = tariffs.MESSAGING_GB * MB_PER_GB  # messaging traffic every tariff includes
MIN_SAVING = Decimal("1.00")  # below this a change is not worth recommending
OVERSIZED = 2  # a plan holding this many times the usage is rejected as too big
CENT = Decimal("0.01")


def money(amount) -> str:
    return f"{Decimal(amount):.2f}"


def gb(data_mb) -> float:
    return round(data_mb / MB_PER_GB, 1)


def _general_mb(m: Metrics) -> float:
    """Monthly data that no slider app and no included messaging accounts for."""
    by_app = m.by_app_mb_month
    messaging_apps = taxonomy.CATEGORIES["messaging"]
    messaging = sum(by_app.get(app, 0) for app in messaging_apps)
    other = sum(
        data_mb
        for app, data_mb in by_app.items()
        if app not in taxonomy.SLIDER_APP.values() and app not in messaging_apps
    )
    return other + max(0.0, messaging - MESSAGING_MB)


def redesign_for(m: Metrics) -> tuple[dict[str, int], bool]:
    """Slider values that fit the usage, and whether they cover all of it.

    Each app slider takes that app's monthly gigabytes; what an app uses beyond
    its slider's maximum is carried by general internet. General internet gets
    headroom on top, calls take the monthly minutes. Every value is rounded up
    to the slider's step and kept inside its range.
    """
    sliders = {slider["key"]: slider for slider in tariffs_catalogue.sliders()}

    def fit(key, wanted) -> int:
        slider = sliders[key]
        stepped = ceil(wanted / slider["step"]) * slider["step"]
        return max(slider["min"], min(slider["max"], stepped))

    values = {}
    general_mb = _general_mb(m)
    for key, app in taxonomy.SLIDER_APP.items():
        used_mb = m.by_app_mb_month.get(app, 0)
        values[key] = fit(key, used_mb / MB_PER_GB)
        general_mb += max(0.0, used_mb - values[key] * MB_PER_GB)
    values["internet"] = fit("internet", general_mb * GENERAL_HEADROOM / MB_PER_GB)
    values["calls"] = fit("calls", m.minutes_month)
    return values, values["internet"] * MB_PER_GB >= general_mb


def current_total(m: Metrics) -> Decimal:
    """What a month costs now: the tariff and the add-on packs bought with it."""
    return m.tariff.price + m.packs_month


def _plan_candidate(plan: Option, title: str, total_now: Decimal, usage_mb: float) -> dict:
    candidate = {
        "id": plan.target_id,
        "title": title,
        "price": money(plan.price),
        "total_month": money(plan.price),
        "saving_month": money(total_now - plan.price),
        "data_gb": plan.data_mb // MB_PER_GB,
        "minutes": plan.minutes,
        "task": {"name": "changeTariff", "params": {"plan": plan.target_id}},
    }
    if usage_mb and plan.data_mb >= OVERSIZED * usage_mb:
        candidate["rejected"] = f"usage_x{plan.data_mb / usage_mb:.1f}"
    return candidate


def advise(m: Metrics, catalogue: Catalogue) -> dict:
    """The current monthly cost against the candidates, and the one to recommend."""
    usage_mb = m.data_mb_month
    total_now = current_total(m)
    candidates = []

    if m.tariff.family == tariffs.ISTESEN:
        values, covered = redesign_for(m)
        price = tariffs.estimate(values)
        candidate = {
            "id": ISTESEN_PLUS,
            "title": "IsteSen+",
            "price": money(price),
            "total_month": money(price),
            "saving_month": money(total_now - price),
            "saving_year": money((total_now - price) * 12),
            "data_gb": sum(value for key, value in values.items() if key != "calls"),
            "minutes": values["calls"],
            "redesign": values,
            "task": {"name": "applyRedesign", "params": values},
        }
        if not covered:
            candidate["rejected"] = "does_not_cover"
        candidates.append(candidate)

    titles = {plan["id"]: plan["title"] for plan in tariffs_catalogue.plans()}
    plans = sorted(
        (plan for plan in catalogue.plans if plan.data_mb and plan.target_id != m.tariff.plan_slug),
        key=lambda plan: plan.price,
    )
    covering = [plan for plan in plans if plan.data_mb >= usage_mb]
    if covering:
        nearest = covering[0]
        candidates.append(_plan_candidate(nearest, titles[nearest.target_id], total_now, usage_mb))
        # The next plan up is listed with the reason it loses, when it is plainly too big.
        for bigger in covering[1:2]:
            bigger_json = _plan_candidate(bigger, titles[bigger.target_id], total_now, usage_mb)
            if "rejected" in bigger_json:
                candidates.append(bigger_json)

    eligible = [candidate for candidate in candidates if "rejected" not in candidate]
    best = min(eligible, key=lambda c: Decimal(c["total_month"]), default=None)
    worth_it = best is not None and Decimal(best["saving_month"]) >= MIN_SAVING
    return {
        "period_days": m.span_days,
        "profile": {
            "data_gb_month": gb(usage_mb),
            "by_app_gb": {app: gb(data_mb) for app, data_mb in sorted(m.by_app_mb_month.items())},
            "minutes_month": round(m.minutes_month),
        },
        "current": {
            "tariff": m.tariff.title,
            "price": money(m.tariff.price),
            "packs_month": money(m.packs_month),
            "total_month": money(total_now),
        },
        "candidates": candidates,
        "recommended": best["id"] if worth_it else "current",
        "effective_from": local_day(m.tariff.next_payment_at).isoformat(),
    }
