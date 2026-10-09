"""Buying packs: charge the wallet and record the activation in one transaction."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from api.billing import services as billing
from api.billing.models import Transaction
from api.common.exceptions import AlreadyActive, InvalidInput, NotFound

from .models import InternetPack, PackActivation, RoamingPack, SocialPack


@dataclass(frozen=True)
class Purchase:
    activation: PackActivation
    transaction: Transaction
    balance: Decimal


def _activate(
    subscriber, *, kind, pack_id, label, title, price, lifetime, auto_renew=False
) -> Purchase:
    tx, balance = billing.charge(
        subscriber, price, title=title, insufficient=_("Not enough balance for this pack")
    )
    now = timezone.now()
    activation = PackActivation.objects.create(
        subscriber=subscriber,
        transaction=tx,
        kind=kind,
        pack_id=pack_id,
        label=label,
        auto_renew=auto_renew,
        activated_at=now,
        expires_at=now + lifetime,
    )
    return Purchase(activation, tx, balance)


@transaction.atomic
def purchase_internet(subscriber, pack_id, price=None) -> Purchase:
    pack = InternetPack.objects.active().filter(slug=pack_id).first()
    if pack is None:
        raise InvalidInput(_("Unknown pack"))
    return _activate(
        subscriber,
        kind="internet",
        pack_id=pack.slug,
        label=pack.label,
        title=_("%(label)s pack") % {"label": pack.label},
        price=pack.price if price is None else price,
        lifetime=timedelta(hours=pack.hours),
        auto_renew=pack.renews,
    )


@transaction.atomic
def activate_social(subscriber, slug, plan_id, price=None) -> Purchase:
    """An auto-renewing social pack can only be active once; the others stack."""
    pack = SocialPack.objects.active().filter(slug=slug).first()
    if pack is None:
        raise NotFound()
    plan = pack.plans.filter(slug=plan_id, is_active=True).first()
    if plan is None:
        raise InvalidInput(_("Unknown plan"))

    # The wallet row is the subscriber's lock: without it two parallel requests
    # could both see "not active yet" and both activate.
    billing.lock_wallet(subscriber)
    already_active = PackActivation.objects.filter(
        subscriber=subscriber,
        kind="social",
        pack_id=slug,
        status="active",
        expires_at__gt=timezone.now(),
    ).exists()
    if pack.auto_renew and already_active:
        raise AlreadyActive(_("This pack is already active"))

    label = f"{pack.title} {plan.title}"
    return _activate(
        subscriber,
        kind="social",
        pack_id=slug,
        label=label,
        title=label,
        price=plan.price if price is None else price,
        lifetime=timedelta(days=plan.days),
        auto_renew=pack.auto_renew,
    )


@transaction.atomic
def purchase_roaming(subscriber, pack_id, price=None) -> Purchase:
    pack = RoamingPack.objects.active().filter(slug=pack_id).first()
    if pack is None:
        raise InvalidInput(_("Unknown pack"))
    label = _("Roaming %(name)s") % {"name": pack.name}
    return _activate(
        subscriber,
        kind="roaming",
        pack_id=pack.slug,
        label=label,
        title=_("%(label)s pack") % {"label": label},
        price=pack.price if price is None else price,
        lifetime=timedelta(days=pack.days),
    )


def expire_activations() -> int:
    """Mark activations past their `expires_at` as expired. Returns how many."""
    return PackActivation.objects.filter(status="active", expires_at__lte=timezone.now()).update(
        status="expired"
    )
