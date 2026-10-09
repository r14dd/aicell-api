from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.billing.idempotency import idempotent
from api.billing.presenters import transaction_brief
from api.common.docs import doc
from api.common.http import iso_local, media, money, validated, validated_query
from api.common.routing import Todo, route

from . import catalogue, services, texts

TAG = "tariffs"


# --- catalogue --------------------------------------------------------------


def family_json(family, plan_id=None):
    plan = services.plan(family, plan_id)
    body = {key: value for key, value in family.items() if key != "default_plan"}
    body.update(
        selected_plan=plan["id"],
        total_price=catalogue.price_groups(),
        note=texts.NOTE,
        cta=_("Subscribe for %(price)s ₼") % {"price": plan["price"]},
    )
    return body


@doc("All tariff families with their plans")
def families(request):
    """Feeds the Change tariff screen and the catalogue pages."""
    return {"results": [family_json(family) for family in catalogue.families()]}


class FamilyQuery(serializers.Serializer):
    plan = serializers.CharField(required=False, help_text="Plan to select, e.g. `digimax-25`")


@doc("One tariff family", query=FamilyQuery, path={"family": "digimax"}, errors=(400, 404))
def family(request, family):
    """`?plan=` selects the chip; without it the family's default plan is selected."""
    plan_id = validated_query(FamilyQuery, request).get("plan")
    return family_json(services.family(family), plan_id)


@doc("Hot offers on tariffs")
def hot(request):
    """Cards of the Products screen, in shelf order."""
    return {"results": catalogue.hot()}


@doc("Change tariff groups and cards")
def change(request):
    """`family_id` is set on cards that open a catalogue page."""
    return {"results": catalogue.change_groups()}


@doc("Premium benefits")
def premium(request):
    """Logo, benefit list and the note under it."""
    return {
        "logo": media(request, "premium-logo.png"),
        "benefits": catalogue.premium_benefits(),
        "note": texts.PREMIUM_NOTE,
    }


# --- my tariff --------------------------------------------------------------


def _ratio(remaining, total) -> float:
    """Share that is left; a redesigned tariff may include none of something."""
    return round(float(remaining) / float(total), 2) if total else 0.0


def _gb(amount) -> str:
    """Whole gigabytes without decimals ("20"), anything else with two ("16.49")."""
    return str(int(amount)) if amount == int(amount) else money(amount)


def usage_rows(tariff):
    return [
        {
            "kind": "internet",
            "label": _("Internet"),
            "remaining": money(tariff.data_remaining_gb),
            "remaining_unit": _("GB"),
            "total": str(tariff.data_total_gb),
            "total_unit": _("GB"),
            "ratio": _ratio(tariff.data_remaining_gb, tariff.data_total_gb),
        },
        {
            "kind": "messaging",
            "label": _("Messaging"),
            "remaining": str(tariff.messaging_remaining_mb),
            "remaining_unit": _("MB"),
            "total": str(tariff.messaging_total_gb),
            "total_unit": _("GB"),
            "ratio": _ratio(tariff.messaging_remaining_mb, tariff.messaging_total_gb * 1024),
        },
        {
            "kind": "calls",
            "label": _("Local calls"),
            "remaining": str(tariff.minutes_remaining),
            "remaining_unit": _("MIN."),
            "total": str(tariff.minutes_total),
            "total_unit": _("MIN."),
            "ratio": _ratio(tariff.minutes_remaining, tariff.minutes_total),
        },
    ]


def _monthly(amount):
    return _("%(amount)s ₼/month") % {"amount": money(amount)}


@doc("My tariff", errors=(404,))
def my(request):
    """Header, usage, payment details, total price, banner and the renew sheet copy."""
    tariff = services.tariff_of(request.user)
    line_type = _("PREPAID") if request.user.line_type == "prepaid" else _("POSTPAID")
    return {
        "family": tariff.family,
        "title": tariff.title,
        "pills": [_("CURRENT TARIFF"), line_type],
        "lines": [
            {"label": _("Current tariff"), "value": _monthly(tariff.price)},
            {"label": _("Next renewal"), "value": _monthly(services.next_price(tariff))},
        ],
        "usage": usage_rows(tariff),
        "payment_details": [
            {
                "label": _("Validity period"),
                "value": _("%(days)s d.") % {"days": tariff.validity_days},
            },
            {"label": _("Activation date"), "value": iso_local(tariff.activated_at)},
            {"label": _("Last payment date"), "value": iso_local(tariff.last_payment_at)},
            {"label": _("Next payment date"), "value": iso_local(tariff.next_payment_at)},
            {"label": _("Payment amount"), "value": money(tariff.price)},
        ],
        "total_price": catalogue.price_groups(),
        "charging_note": texts.CHARGING_NOTE,
        "banner": {
            "image": media(request, "banner-want-more.png"),
            "alt": texts.BANNER_ALT,
            "deep_link": "/internet-packs",
        },
        "renew": texts.RENEW,
    }


@doc("Remaining balance of my tariff", errors=(404,))
def usage(request):
    """Home card, Remaining balance page and the aggregation sheet copy.

    `remaining.data_gb` and `data_total_gb` add the active internet packs to the
    tariff, as the aggregation sheet says; `rows` are the tariff alone.
    """
    tariff = services.tariff_of(request.user)
    data_left, data_total = services.data_with_packs(request.user, tariff)
    left = services.period_left(tariff)
    renews_at = timezone.localtime(tariff.next_payment_at)
    return {
        "tariff": tariff.title,
        "renewal_label": _("Renews %(day)s, %(time)s")
        % {"day": services.renewal_day(tariff), "time": f"{renews_at:%H:%M}"},
        "period_left": {"days": left.days, "hours": left.seconds // 3600},
        "remaining": {
            "data_gb": money(data_left),
            "data_total_gb": _gb(data_total),
            "minutes": tariff.minutes_remaining,
            "minutes_total": tariff.minutes_total,
        },
        "rows": usage_rows(tariff),
        "aggregation": texts.AGGREGATION,
    }


def redesign_json(tariff):
    return {
        "sliders": [
            {**slider, "value": tariff.redesign.get(slider["key"], slider["min"])}
            for slider in catalogue.sliders()
        ],
        "pricing": services.REDESIGN_PRICING,
        "estimate": money(services.estimate(tariff.redesign)),
    }


@doc("Redesign sliders and current estimate", errors=(404,))
def redesign(request):
    """The client computes the live estimate with `pricing`."""
    return redesign_json(services.tariff_of(request.user))


class RedesignInput(serializers.Serializer):
    values = serializers.DictField(
        child=serializers.IntegerField(), help_text="One whole number per slider `key`"
    )


@doc(
    "Save a redesigned tariff",
    body=RedesignInput,
    example={"values": {"internet": 10, "calls": 100, "instagramFb": 5, "youtube": 2, "tiktok": 0}},
    errors=(400, 404),
)
def redesign_save(request):
    """Stores the sliders ("Save: 19.10 ₼"). Nothing is charged: the new price and amounts
    apply from the next renewal, and `my/` shows the price as "Next renewal"."""
    values = validated(RedesignInput, request)["values"]
    return redesign_json(services.save_redesign(request.user, values))


# --- paying for a tariff ----------------------------------------------------


def paid_json(paid):
    tariff = paid.tariff
    return {
        "tariff": {
            "family": tariff.family,
            "plan_id": tariff.plan_slug or None,
            "title": tariff.title,
            "price": money(tariff.price),
            "validity_days": tariff.validity_days,
            "activated_at": iso_local(tariff.activated_at),
            "next_payment_at": iso_local(tariff.next_payment_at),
        },
        "transaction": transaction_brief(paid.transaction),
        "balance": money(paid.balance),
    }


class PlanChoice(serializers.Serializer):
    plan_id = serializers.CharField(help_text="`id` of a plan from `catalogue/`")


@doc(
    "Subscribe to a tariff plan",
    body=PlanChoice,
    example={"plan_id": "digimax-5"},
    errors=(400, 402, 409),
    status=201,
)
@idempotent
def subscribe(request):
    """Charges the plan's price and replaces the current tariff ("Subscribe for X ₼").
    What was left of the old tariff is annulled; active packs stay."""
    plan_id = validated(PlanChoice, request)["plan_id"]
    return paid_json(services.subscribe(request.user, plan_id)), 201


class TariffChoice(serializers.Serializer):
    tariff_id = serializers.CharField(help_text="`id` of a card whose `family_id` is null")


@doc(
    "Change to a tariff without a catalogue page",
    body=TariffChoice,
    example={"tariff_id": "digimax-3gb"},
    errors=(400, 402, 409),
    status=201,
)
@idempotent
def change_to(request):
    """Charges the card's price and replaces the current tariff. A card with a
    `family_id` is `400`: its plans are chosen with `subscribe/`."""
    tariff_id = validated(TariffChoice, request)["tariff_id"]
    return paid_json(services.change(request.user, tariff_id)), 201


@doc("Renew my tariff", errors=(400, 402, 404), status=201)
@idempotent
def renew(request):
    """Pays for a new period now (Renew tariff sheet → Renew): amounts are back to
    full and the dates move on. IsteSen renews with its saved slider values."""
    return paid_json(services.renew(request.user)), 201


# --- routes -----------------------------------------------------------------

catalogue_view = route(TAG, get=families)
catalogue_family_view = route(TAG, get=family)
hot_view = route(TAG, get=hot)
subscribe_view = route(TAG, post=subscribe)
my_view = route(TAG, get=my)
usage_view = route(TAG, get=usage)
renew_view = route(TAG, post=renew)
redesign_view = route(TAG, get=redesign, post=redesign_save)
change_view = route(TAG, get=change, post=change_to)
premium_view = route(TAG, get=premium)
premium_activate_view = route(
    TAG,
    post=Todo(_("Premium activation is not part of this prototype yet"), "Activate Premium"),
)
