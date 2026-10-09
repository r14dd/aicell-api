from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.common.docs import doc
from api.common.exceptions import NotFound
from api.common.http import iso_local, validated
from api.common.routing import route
from api.kredit.models import KreditProduct
from api.usage import offers as catalogue_items

from . import advisor, services
from .catalogue import HOURS_PER_DAY, Catalogue
from .metrics import metrics

TAG = "insights"
SAMPLE_ID = 7001  # the seeded demo subscriber's insight (`seeding.DEMO_INSIGHT_ID`)
CATALOGUE_KINDS = ("internet_pack", "social_pack", "roaming_pack", "tariff_plan")
# Internal fields of a stored offer that the label and validity are made from.
HIDDEN = ("kind", "target_id", "hours")


def _label(offer) -> str | None:
    """The offer's name in the reader's language; None when it can no longer be had."""
    kind = offer["kind"]
    if kind in CATALOGUE_KINDS:
        target = catalogue_items.resolve(kind, offer["target_id"])
        return target and target.title
    if kind == "redesign":
        return "IsteSen+"
    if kind == "top_up":
        return _("Top up %(amount)s ₼") % {"amount": offer["price"]}
    kredit = KreditProduct.objects.active().filter(slug=offer["target_id"]).first()
    return kredit and kredit.name


def _validity(hours) -> str | None:
    if not hours:
        return None
    if hours % HOURS_PER_DAY == 0:
        return _("%(days)s d.") % {"days": hours // HOURS_PER_DAY}
    return _("%(hours)s h.") % {"hours": hours}


def offer_json(offer) -> dict | None:
    label = _label(offer)
    if label is None:
        return None
    shown = {key: value for key, value in offer.items() if key not in HIDDEN}
    return {
        "ref": offer["ref"],
        "label": label,
        "price": offer["price"],
        "validity": _validity(offer.get("hours")),
        **{key: value for key, value in shown.items() if key not in ("ref", "price")},
    }


def insight_json(insight) -> dict | None:
    """An insight as the app gets it; None when none of its offers can be had any more."""
    offers = [(index, offer_json(offer)) for index, offer in enumerate(insight.offers)]
    offers = [(index, offer) for index, offer in offers if offer is not None]
    if not offers:
        return None
    positions = [index for index, _offer in offers]
    recommended = insight.recommended
    return {
        "id": insight.id,
        "kind": insight.kind,
        "severity": insight.severity,
        "status": insight.status,
        "created_at": iso_local(insight.created_at),
        "expires_at": iso_local(insight.expires_at),
        "evidence": insight.evidence,
        "offers": [offer for _index, offer in offers],
        "recommended": positions.index(recommended) if recommended in positions else 0,
    }


@doc("Insights to show now")
def insights(request):
    """What the subscriber's own usage shows, each with priced offers from the catalogue.

    The detectors run on every call, so a purchase or a top-up is reflected at
    once. Urgent insights come first; at most one new `info` insight is given
    per 48 hours and nothing between 23:00 and 08:00 (Asia/Baku). There are no
    sentences here: `evidence` and `offers` are the facts to word.
    """
    services.refresh(request.user)
    shown = (insight_json(insight) for insight in services.deliverable(request.user))
    return {"results": [insight for insight in shown if insight is not None]}


@doc("Mark an insight as shown", path={"id": SAMPLE_ID}, errors=(404,))
def seen(request, id):
    """The app showed it (the assistant's balloon, a card, a notification)."""
    return insight_json(services.mark_seen(request.user, id))


class AcceptInput(serializers.Serializer):
    offer = serializers.IntegerField(
        required=False, min_value=0, help_text="Index into `offers`; the recommended one if absent"
    )


@doc(
    "Accept an insight's offer",
    body=AcceptInput,
    example={"offer": 0},
    path={"id": SAMPLE_ID},
    errors=(400, 404),
)
def accept(request, id):
    """Records the "yes" and returns the offer's `task`. Nothing is charged here:
    the task is carried out with the endpoint that sells it (`packs/…/purchase/`,
    `tariffs/subscribe/`, `tariffs/my/redesign/`, `billing/top-up/…`)."""
    choice = validated(AcceptInput, request).get("offer")
    insight = services.accept(request.user, id, choice)
    body = insight_json(insight) or {"id": insight.id, "status": insight.status}
    return {**body, "task": insight.offers[insight.accepted_offer]["task"]}


@doc("Dismiss an insight", path={"id": SAMPLE_ID}, errors=(404,))
def dismiss(request, id):
    """Records the "no". No insight of the same kind is written for 14 days."""
    insight = services.dismiss(request.user, id)
    return insight_json(insight) or {"id": insight.id, "status": insight.status}


@doc("The tariff setup that fits the usage", errors=(404,))
def advise(request):
    """Compares what a month costs now with IsteSen redesigned to the usage
    ("IsteSen+") and with the cheapest catalogue plan that covers it.
    `recommended` is a candidate's `id`, or `current` when a change saves less than 1 ₼."""
    figures = metrics(request.user)
    if figures is None:
        raise NotFound()
    return advisor.advise(figures, Catalogue.load())


insights_view = route(TAG, get=insights)
seen_view = route(TAG, post=seen)
accept_view = route(TAG, post=accept)
dismiss_view = route(TAG, post=dismiss)
advisor_view = route(TAG, get=advise)
