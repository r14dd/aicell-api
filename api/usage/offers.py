"""Personal offers: a catalogue item at a special price, for one subscriber, for a while.

Staff define rules by segment in the admin. `refresh` (a beat task) gives every
matching subscriber an offer, expires old ones and announces new ones with a
notification. A subscriber has at most one open offer, and gets no new one for
`COOLDOWN_DAYS` after declining one or letting one expire.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from api.billing import services as billing
from api.common.exceptions import NotFound, OfferClosed
from api.common.formatting import money
from api.content.models import Notification
from api.packs import services as packs
from api.packs.models import InternetPack, RoamingPack, SocialPlan
from api.packs.services import Purchase
from api.tariffs.models import TariffPlan
from api.users.models import Subscriber

from . import services
from .models import OfferRule, PersonalOffer

COOLDOWN_DAYS = 7


@dataclass(frozen=True)
class Target:
    """The catalogue item an offer is for."""

    title: str
    price: Decimal
    family_id: str = ""


def resolve(kind: str, target_id: str) -> Target | None:
    """Look the offered item up in the catalogue; None when it is gone or switched off."""
    if kind == "internet_pack":
        pack = InternetPack.objects.active().filter(slug=target_id).first()
        return pack and Target(pack.label, pack.price)
    if kind == "roaming_pack":
        pack = RoamingPack.objects.active().filter(slug=target_id).first()
        return pack and Target(_("Roaming %(name)s") % {"name": pack.name}, pack.price)
    if kind == "social_pack":
        pack_slug, _sep, plan_slug = target_id.partition(":")
        plan = (
            SocialPlan.objects.active()
            .filter(pack__slug=pack_slug, pack__is_active=True, slug=plan_slug)
            .select_related("pack")
            .first()
        )
        return plan and Target(f"{plan.pack.title} {plan.title}", plan.price)
    if kind == "tariff_plan":
        plan = TariffPlan.objects.active().filter(slug=target_id).select_related("family").first()
        return plan and Target(plan.title, plan.price, plan.family.slug)
    return None


def reason_of(offer: PersonalOffer) -> str:
    return offer.rule.reason if offer.rule else offer.reason


# --- lifecycle ----------------------------------------------------------------


def expire_due(now=None) -> int:
    """Close open offers whose time has passed. Returns how many."""
    now = now or timezone.now()
    return PersonalOffer.objects.filter(status__in=PersonalOffer.OPEN, expires_at__lte=now).update(
        status="expired"
    )


def open_offer(subscriber) -> PersonalOffer | None:
    """The subscriber's open offer, if there is one that has not run out."""
    expire_due()
    return (
        PersonalOffer.objects.filter(subscriber=subscriber, status__in=PersonalOffer.OPEN)
        .select_related("rule")
        .order_by("-id")
        .first()
    )


def mark_shown(offer: PersonalOffer) -> None:
    if offer.status == "new":
        offer.status = "shown"
        offer.save(update_fields=["status"])


def _in_cooldown(subscriber, now) -> bool:
    since = now - timedelta(days=COOLDOWN_DAYS)
    offers = PersonalOffer.objects.filter(subscriber=subscriber)
    return (
        offers.filter(status="declined", decided_at__gte=since).exists()
        or offers.filter(status="expired", expires_at__gte=since).exists()
    )


def _announce(offer: PersonalOffer, target: Target) -> None:
    """Tell the subscriber, in every language, with a link to the offer."""
    fields = {}
    for language, _name in settings.LANGUAGES:
        with translation.override(language):
            fields[f"title_{language}"] = _("A personal offer for you")
            fields[f"body_{language}"] = _(
                "%(title)s for %(offer)s ₼ instead of %(normal)s ₼. %(reason)s"
            ) % {
                "title": resolve(offer.target_kind, offer.target_id).title,
                "offer": money(offer.offer_price),
                "normal": money(offer.normal_price),
                "reason": reason_of(offer),
            }
            fields[f"cta_{language}"] = {
                "label": _("See the offer"),
                "deep_link": f"/offers/{offer.id}",
            }
    Notification.objects.create(subscriber=offer.subscriber, slug=f"offer-{offer.id}", **fields)


def create_offer(subscriber, rule: OfferRule, now=None) -> PersonalOffer | None:
    """Give the subscriber the rule's offer; None when its item is not in the catalogue."""
    now = now or timezone.now()
    target = resolve(rule.target_kind, rule.target_id)
    if target is None:
        return None
    offer = PersonalOffer.objects.create(
        subscriber=subscriber,
        rule=rule,
        target_kind=rule.target_kind,
        target_id=rule.target_id,
        normal_price=target.price,
        offer_price=rule.offer_price,
        reason=rule.reason,
        created_at=now,
        expires_at=now + timedelta(days=rule.valid_days),
    )
    _announce(offer, target)
    return offer


@transaction.atomic
def refresh(now=None) -> dict[str, int]:
    """Expire old offers and create the ones the rules call for."""
    now = now or timezone.now()
    expired = expire_due(now)
    rules = list(OfferRule.objects.active())
    created = 0
    if rules:
        for subscriber in Subscriber.objects.filter(is_staff=False, is_active=True):
            taken = PersonalOffer.objects.filter(subscriber=subscriber)
            if taken.filter(status__in=PersonalOffer.OPEN).exists():
                continue  # at most one open offer
            if _in_cooldown(subscriber, now):
                continue
            segment = services.profile(subscriber).segment
            accepted = set(taken.filter(status="accepted").values_list("rule_id", flat=True))
            for rule in rules:
                if rule.segment == segment and rule.id not in accepted:
                    created += bool(create_offer(subscriber, rule, now))
                    break
    return {"created": created, "expired": expired}


# --- the subscriber's answer --------------------------------------------------


@dataclass(frozen=True)
class Accepted:
    offer: PersonalOffer
    purchase: Purchase | None  # None for a tariff offer: nothing is bought here


def _own_open(subscriber, offer_id) -> PersonalOffer:
    """The subscriber's own offer, still open. Someone else's is simply not found."""
    offer = (
        PersonalOffer.objects.filter(subscriber=subscriber, id=offer_id)
        .select_related("rule")
        .first()
    )
    if offer is None:
        raise NotFound()
    # An offer past its time is closed whether or not `expire_due` has marked it
    # yet. Marking it here would be undone by the error that follows.
    if offer.status not in PersonalOffer.OPEN or offer.expires_at <= timezone.now():
        raise OfferClosed()
    return offer


@transaction.atomic
def accept(subscriber, offer_id) -> Accepted:
    """Buy the offered pack at the offer price, exactly like a normal purchase.

    A tariff offer buys nothing: a tariff at an offer price is not built, so the caller
    only gets the way to the tariff's page and the offer stays open.
    """
    billing.lock_wallet(subscriber)  # one answer at a time per subscriber
    offer = _own_open(subscriber, offer_id)
    if offer.target_kind == "tariff_plan":
        return Accepted(offer, None)

    price = offer.offer_price
    if offer.target_kind == "internet_pack":
        purchase = packs.purchase_internet(subscriber, offer.target_id, price=price)
    elif offer.target_kind == "roaming_pack":
        purchase = packs.purchase_roaming(subscriber, offer.target_id, price=price)
    else:
        pack_slug, _sep, plan_slug = offer.target_id.partition(":")
        purchase = packs.activate_social(subscriber, pack_slug, plan_slug, price=price)

    offer.status = "accepted"
    offer.decided_at = timezone.now()
    offer.activation = purchase.activation
    offer.save(update_fields=["status", "decided_at", "activation"])
    return Accepted(offer, purchase)


@transaction.atomic
def decline(subscriber, offer_id) -> PersonalOffer:
    offer = _own_open(subscriber, offer_id)
    offer.status = "declined"
    offer.decided_at = timezone.now()
    offer.save(update_fields=["status", "decided_at"])
    return offer
