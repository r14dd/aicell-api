"""The subscriber's tariff: what it holds, and paying for a new period or another tariff."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from api.billing import services as billing
from api.billing.models import Transaction
from api.common.exceptions import AlreadyActive, InvalidInput, NotFound
from api.packs.models import InternetPack, PackActivation

from . import catalogue
from .models import ChangeCard, SubscriberTariff, TariffPlan

ISTESEN = "istesen"  # the tariff the subscriber designs with sliders; it has no catalogue plan
MB_PER_GB = 1024
PERIOD_DAYS = 28
PREMIUM_PERIOD_DAYS = 30
MESSAGING_GB = 1  # every tariff includes this much messaging traffic

# Redesign: the base price covers INCLUDED; each unit away from it moves the price.
REDESIGN_PRICING = {"base": "19.10", "per_gb": "0.50", "per_minute": "0.02"}
REDESIGN_INCLUDED = {"internet": 16, "calls": 30}


def tariff_of(subscriber) -> SubscriberTariff:
    tariff = SubscriberTariff.objects.filter(subscriber=subscriber).first()
    if tariff is None:
        raise NotFound()
    return tariff


def family(family_id) -> dict:
    found = next((item for item in catalogue.families() if item["id"] == family_id), None)
    if found is None:
        raise NotFound()
    return found


def plan(family: dict, plan_id=None) -> dict:
    """The selected plan of a family; its default one when none is asked for."""
    plan_id = plan_id or family["default_plan"]
    found = next((plan for plan in family["plans"] if plan["id"] == plan_id), None)
    if found is None:
        raise InvalidInput(_("Unknown plan '%(plan)s'") % {"plan": plan_id})
    return found


def estimate(values: dict) -> Decimal:
    """Monthly price of a redesigned tariff."""
    pricing = {key: Decimal(value) for key, value in REDESIGN_PRICING.items()}
    # A stored redesign may lack keys: the included amounts and no socials.
    internet = values.get("internet", REDESIGN_INCLUDED["internet"])
    calls = values.get("calls", REDESIGN_INCLUDED["calls"])
    socials = sum(values.get(key, 0) for key in ("instagramFb", "youtube", "tiktok"))
    extra_gb = internet - REDESIGN_INCLUDED["internet"] + socials
    extra_minutes = calls - REDESIGN_INCLUDED["calls"]
    return pricing["base"] + pricing["per_gb"] * extra_gb + pricing["per_minute"] * extra_minutes


def renewal_day(tariff) -> str:
    """Next payment day in Asia/Baku in the active language, e.g. `25 October`."""
    # "E" is the month as it reads after a day number: Russian needs the
    # genitive ("25 октября"), which the plain month name "F" does not give.
    return date_format(timezone.localtime(tariff.next_payment_at), "j E")


def period_left(tariff) -> timedelta:
    return max(tariff.next_payment_at - timezone.now(), timedelta(0))


def next_price(tariff) -> Decimal:
    """What the next period will cost: the sliders for IsteSen, the catalogue for a plan."""
    if tariff.family == ISTESEN:
        return estimate(tariff.redesign)
    plan = TariffPlan.objects.active().filter(slug=tariff.plan_slug).first()
    return plan.price if plan else tariff.price


def data_with_packs(subscriber, tariff) -> tuple[Decimal, Decimal]:
    """Internet left and in total, in GB: the tariff plus every active internet pack.

    This is the sum the aggregation sheet describes. How much of a pack has
    been used is not tracked, so an active pack counts in full on both sides.
    Unlimited packs have no amount to add.
    """
    active = PackActivation.objects.filter(
        subscriber=subscriber, kind="internet", status="active", expires_at__gt=timezone.now()
    ).values_list("pack_id", flat=True)
    sizes = dict(InternetPack.objects.filter(slug__in=set(active)).values_list("slug", "data_mb"))
    packs_gb = Decimal(sum(sizes.get(pack_id) or 0 for pack_id in active)) / MB_PER_GB
    return tariff.data_remaining_gb + packs_gb, tariff.data_total_gb + packs_gb


# --- paying for a tariff ------------------------------------------------------


@dataclass(frozen=True)
class Terms:
    """What a tariff period costs and holds."""

    family: str
    plan_slug: str
    title: str
    price: Decimal
    validity_days: int
    data_gb: int
    minutes: int


@dataclass(frozen=True)
class Paid:
    tariff: SubscriberTariff
    transaction: Transaction
    balance: Decimal


def _minutes(included, validity_days: int) -> int:
    # Unlimited calls have no number; every minute of the period is the most one can use.
    return validity_days * 24 * 60 if included is None else included


def _plan_terms(plan: TariffPlan) -> Terms:
    days = PREMIUM_PERIOD_DAYS if plan.family.is_premium else PERIOD_DAYS
    return Terms(
        family=plan.family.slug,
        plan_slug=plan.slug,
        title=plan.title,
        price=plan.price,
        validity_days=days,
        data_gb=plan.data_mb // MB_PER_GB,
        minutes=_minutes(plan.minutes, days),
    )


def _start_period(subscriber, terms: Terms, *, title: str, current=None) -> Paid:
    """Charge the wallet and begin a full period on `terms`.

    The charge comes first: without the money nothing about the tariff changes.
    What was left of the old period is annulled, as the renew sheet says.
    """
    tx, balance = billing.charge(
        subscriber, terms.price, title=title, insufficient=_("Not enough balance for this tariff")
    )
    now = timezone.now()
    tariff = current or SubscriberTariff(subscriber=subscriber)
    switched = current is None or (current.family, current.plan_slug) != (
        terms.family,
        terms.plan_slug,
    )
    if switched:
        tariff.activated_at = now
    tariff.family = terms.family
    tariff.plan_slug = terms.plan_slug
    tariff.title = terms.title
    tariff.price = terms.price
    tariff.validity_days = terms.validity_days
    tariff.last_payment_at = now
    tariff.next_payment_at = now + timedelta(days=terms.validity_days)
    tariff.data_total_gb = terms.data_gb
    tariff.data_remaining_gb = terms.data_gb
    tariff.messaging_total_gb = MESSAGING_GB
    tariff.messaging_remaining_mb = MESSAGING_GB * MB_PER_GB
    tariff.minutes_total = terms.minutes
    tariff.minutes_remaining = terms.minutes
    tariff.save()
    return Paid(tariff, tx, balance)


def _current(subscriber) -> SubscriberTariff | None:
    """The subscriber's tariff, read under the wallet lock so two switches cannot interleave."""
    billing.lock_wallet(subscriber)
    return SubscriberTariff.objects.filter(subscriber=subscriber).first()


def _tariff_title(title: str) -> str:
    return _("%(title)s tariff") % {"title": title}


@transaction.atomic
def subscribe(subscriber, plan_id: str) -> Paid:
    """Move the subscriber to a catalogue plan, paying its price."""
    plan = (
        TariffPlan.objects.active()
        .filter(slug=plan_id, family__is_active=True)
        .select_related("family")
        .first()
    )
    if plan is None:
        raise InvalidInput(_("Unknown plan"))
    if plan.data_mb is None:
        raise InvalidInput(_("This tariff cannot be chosen in the app yet"))
    current = _current(subscriber)
    if current and current.plan_slug == plan.slug:
        raise AlreadyActive(_("You are already on this tariff"))
    return _start_period(
        subscriber, _plan_terms(plan), title=_tariff_title(plan.title), current=current
    )


@transaction.atomic
def change(subscriber, tariff_id: str) -> Paid:
    """Move the subscriber to a Change tariff card that has no catalogue page."""
    card = (
        ChangeCard.objects.active().filter(slug=tariff_id).select_related("family", "group").first()
    )
    if card is None:
        raise InvalidInput(_("Unknown tariff"))
    if card.family is not None:
        raise InvalidInput(_("This tariff has plans: choose one on its page"))
    if card.data_mb is None or card.minutes is None or not card.price.replace(".", "", 1).isdigit():
        raise InvalidInput(_("This tariff cannot be chosen in the app yet"))
    current = _current(subscriber)
    if current and current.plan_slug == card.slug:
        raise AlreadyActive(_("You are already on this tariff"))
    terms = Terms(
        family=card.group.slug,
        plan_slug=card.slug,
        title=card.title,
        price=Decimal(card.price),
        validity_days=card.validity_days,
        data_gb=card.data_mb // MB_PER_GB,
        minutes=card.minutes,
    )
    return _start_period(subscriber, terms, title=_tariff_title(card.title), current=current)


@transaction.atomic
def renew(subscriber) -> Paid:
    """Pay for a new period of the current tariff now; what was left is annulled.

    IsteSen renews at the price and amounts of its saved sliders, so this is
    where a redesign takes effect.
    """
    current = _current(subscriber)
    if current is None:
        raise NotFound()
    if current.family == ISTESEN:
        terms = Terms(
            family=ISTESEN,
            plan_slug="",
            title=current.title,
            price=estimate(current.redesign),
            validity_days=current.validity_days,
            data_gb=current.redesign["internet"],
            minutes=current.redesign["calls"],
        )
    else:
        terms = Terms(
            family=current.family,
            plan_slug=current.plan_slug,
            title=current.title,
            price=next_price(current),
            validity_days=current.validity_days,
            data_gb=current.data_total_gb,
            minutes=current.minutes_total,
        )
    title = _("%(title)s tariff renewal") % {"title": current.title}
    return _start_period(subscriber, terms, title=title, current=current)


# --- redesign -----------------------------------------------------------------


def save_redesign(subscriber, values: dict) -> SubscriberTariff:
    """Store the slider values of IsteSen. They cost nothing now and apply at the next renewal."""
    tariff = tariff_of(subscriber)
    if tariff.family != ISTESEN:
        raise InvalidInput(_("Only the IsteSen tariff can be redesigned"))
    sliders = {slider["key"]: slider for slider in catalogue.sliders()}
    errors = {key: [_("Unknown slider")] for key in values if key not in sliders}
    for key, slider in sliders.items():
        if key not in values:
            errors[key] = [_("Give a value for this slider")]
        elif (
            not slider["min"] <= values[key] <= slider["max"]
            or (values[key] - slider["min"]) % slider["step"]
        ):
            errors[key] = [
                _("Must be between %(min)s and %(max)s in steps of %(step)s")
                % {"min": slider["min"], "max": slider["max"], "step": slider["step"]}
            ]
    if errors:
        raise InvalidInput(errors={"values": errors})
    tariff.redesign = {key: values[key] for key in sliders}
    tariff.save(update_fields=["redesign"])
    return tariff
