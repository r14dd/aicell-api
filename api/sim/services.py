"""SIM rules: call forwarding, roaming and paid service subscriptions."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from api.billing import services as billing
from api.billing.models import Transaction
from api.common.exceptions import AlreadyActive, InvalidInput, NotFound

from .models import ServiceSubscription, SimProfile, SimService

FORWARDING = ("all", "unanswered", "busy", "unreachable")
CONDITIONAL = FORWARDING[1:]


def sim_of(subscriber) -> SimProfile:
    sim = SimProfile.objects.filter(subscriber=subscriber).first()
    if sim is None:
        raise NotFound()
    return sim


def forwarding_of(sim) -> dict[str, bool]:
    return {name: getattr(sim, f"forward_{name}") for name in FORWARDING}


def update_call_forwarding(sim, changes: dict[str, bool]) -> SimProfile:
    """Apply forwarding toggles. Forwarding all calls wins over the conditional three.

    Turning "all" on resets the others. While it is on, a request that turns a
    conditional toggle on without also turning "all" off is rejected.
    """
    all_calls = changes.get("all", sim.forward_all)
    if all_calls:
        if "all" not in changes and any(changes.get(name) for name in CONDITIONAL):
            raise InvalidInput(_("Turn off forwarding of all calls first"))
        changes = {"all": True, **dict.fromkeys(CONDITIONAL, False)}
    for name, value in changes.items():
        setattr(sim, f"forward_{name}", value)
    sim.save()
    return sim


def set_roaming(sim, enabled: bool) -> SimProfile:
    if enabled != sim.roaming_enabled:
        sim.roaming_enabled = enabled
        sim.roaming_changed_at = timezone.now()
        sim.save(update_fields=["roaming_enabled", "roaming_changed_at"])
    return sim


# --- services ---------------------------------------------------------------


@dataclass(frozen=True)
class ServicePurchase:
    subscription: ServiceSubscription
    transaction: Transaction
    balance: Decimal


def active_service_ids(subscriber) -> set[str]:
    return set(
        ServiceSubscription.objects.filter(subscriber=subscriber, status="active").values_list(
            "service", flat=True
        )
    )


def offered_options(service: SimService) -> set[str]:
    return {section["option"]["id"] for section in service.sections if "option" in section}


@transaction.atomic
def subscribe(subscriber, slug, options: list[str]) -> ServicePurchase:
    service = SimService.objects.active().filter(slug=slug).first()
    if service is None:
        raise NotFound()
    if set(options) - offered_options(service):
        raise InvalidInput(_("Unknown option"))

    # The wallet row is the subscriber's lock: without it two parallel requests
    # could both see "not active yet" and both subscribe.
    billing.lock_wallet(subscriber)
    if slug in active_service_ids(subscriber):
        raise AlreadyActive(_("This service is already active"))

    tx, balance = billing.charge(
        subscriber,
        service.price,
        title=_("%(name)s service") % {"name": service.name},
        insufficient=_("Not enough balance for this service"),
    )
    subscription = ServiceSubscription.objects.create(
        subscriber=subscriber,
        transaction=tx,
        service=slug,
        options=options,
        next_payment_at=timezone.now() + timedelta(days=service.days),
    )
    return ServicePurchase(subscription, tx, balance)
