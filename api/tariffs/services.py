"""Calculations on the subscriber's tariff."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from api.common.exceptions import InvalidInput, NotFound

from . import catalogue
from .models import SubscriberTariff

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
