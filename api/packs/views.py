from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.billing.idempotency import idempotent
from api.billing.presenters import transaction_brief
from api.common.docs import doc
from api.common.exceptions import NotFound
from api.common.http import iso, money, validated
from api.common.routing import Todo, route

from . import catalogue, services, texts

TAG = "packs"


def purchase_json(purchase):
    activation = purchase.activation
    return {
        "activation": {
            "id": activation.id,
            "pack_id": activation.pack_id,
            "label": activation.label,
            "status": activation.status,
            "activated_at": iso(activation.activated_at),
            "expires_at": iso(activation.expires_at),
            "auto_renew": activation.auto_renew,
        },
        "transaction": transaction_brief(purchase.transaction),
        "balance": money(purchase.balance),
    }


class PackInput(serializers.Serializer):
    pack_id = serializers.CharField(help_text="`id` of a pack from the list")


class PlanInput(serializers.Serializer):
    plan_id = serializers.CharField(help_text="`id` of one of the pack's plans")


# --- internet ---------------------------------------------------------------


@doc("Internet packs page")
def internet(request):
    """Promo, categories, packs per category and the social pack cards.

    `msisdn` is the "For number" line of the confirmation sheet.
    """
    return {
        "promo": texts.PROMO,
        "categories": catalogue.categories(),
        "packs": catalogue.internet_packs(),
        "social": [
            {key: value for key, value in pack.items() if key != "plans"}
            for pack in catalogue.social_packs()
        ],
        "msisdn": request.user.msisdn,
    }


@doc("TOP internet packs")
def internet_top(request):
    """The three packs of the Products screen."""
    return {"results": catalogue.top()}


@doc(
    "Buy an internet pack",
    body=PackInput,
    example={"pack_id": "unlimited-1h"},
    errors=(400, 402),
    status=201,
)
@idempotent
def internet_purchase(request):
    """Charges the wallet and activates the pack ("Confirm your payment" → Confirm)."""
    pack_id = validated(PackInput, request)["pack_id"]
    return purchase_json(services.purchase_internet(request.user, pack_id)), 201


# --- social -----------------------------------------------------------------


@doc("Social pack detail", path={"slug": "tehsil"}, errors=(404,))
def social(request, slug):
    """The rows describe the default plan; the client updates them for the selected one."""
    pack = next((pack for pack in catalogue.social_packs() if pack["id"] == slug), None)
    if pack is None or not pack["plans"]:
        raise NotFound()
    plan = pack["plans"][0]
    return {
        "id": pack["id"],
        "title": pack["title"],
        "app": pack["app"],
        "badge": _("AUTO-RENEWAL") if pack["auto_renew"] else None,
        "rows": [
            {"label": _("Application traffic"), "value": plan["title"]},
            {"label": _("Validity period"), "value": plan["validity"]},
            {
                "label": _("Renews"),
                "value": _("Automatically") if pack["auto_renew"] else _("Manually"),
            },
        ],
        "note": texts.NOTE,
        "plans": pack["plans"],
        "default_plan": plan["id"],
        "cta": pack["cta"],
    }


@doc(
    "Activate a social pack",
    body=PlanInput,
    example={"plan_id": "100gb"},
    path={"slug": "tehsil"},
    errors=(400, 402, 404, 409),
    status=201,
)
@idempotent
def social_activate(request, slug):
    """An auto-renewing pack that is already active answers `409 already_active`."""
    plan_id = validated(PlanInput, request)["plan_id"]
    return purchase_json(services.activate_social(request.user, slug, plan_id)), 201


# --- roaming ----------------------------------------------------------------


@doc("Roaming packs")
def roaming(request):
    """The list and the copy of the "not yet in the roaming area" confirmation."""
    return {"results": catalogue.roaming(), "confirm": texts.ROAMING_CONFIRM}


@doc(
    "Buy a roaming pack",
    body=PackInput,
    example={"pack_id": "r-500mb"},
    errors=(400, 402),
    status=201,
)
@idempotent
def roaming_purchase(request):
    """Charges the wallet and activates the pack immediately."""
    pack_id = validated(PackInput, request)["pack_id"]
    return purchase_json(services.purchase_roaming(request.user, pack_id)), 201


# --- routes -----------------------------------------------------------------

internet_view = route(TAG, get=internet)
internet_top_view = route(TAG, get=internet_top)
internet_purchase_view = route(TAG, post=internet_purchase)
social_view = route(TAG, get=social)
social_activate_view = route(TAG, post=social_activate)
roaming_view = route(TAG, get=roaming)
roaming_purchase_view = route(TAG, post=roaming_purchase)
active_view = route(
    TAG, get=Todo(_("Active packs are not part of this prototype yet"), "My active packs")
)
